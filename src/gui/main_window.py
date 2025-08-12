from PyQt6.QtWidgets import (
    QApplication,
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QFileDialog, QGridLayout,
    QLineEdit, QMessageBox, QSystemTrayIcon, QHBoxLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from src.core.config_store import ConfigStore
from src.core.audio_player import AudioPlayer
from src.core.device_listener import DeviceListener, MultiDeviceListener
from src.core.types import EventSignature
from src.core.hid_devices import list_hid_devices
from .tray import TrayController


class MainWindow(QWidget):
    capture_ready = pyqtSignal(int, object)  # (row_idx, EventSignature)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Soundpad - Practica de libro by Aragon")
        self.resize(720, 520)

        # state
        self.config = ConfigStore()
        self.audio = AudioPlayer()
        self.listener = None
        self._was_listening = False
        self._capture_listener = None
        self.device_map = []

        # ui and wiring
        self._build_ui()
        self._load_config()
        self._populate_devices()
        self._wire_tray()
        # wire capture signal
        self.capture_ready.connect(self._on_capture_ready)

    def _build_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Selecciona dispositivo (HID/Global)"))
        self.device_selector = QComboBox()
        layout.addWidget(self.device_selector)

        self.grid = QGridLayout()
        self.grid.addWidget(QLabel("#"), 0, 0)
        self.grid.addWidget(QLabel("Botón/Tecla"), 0, 1)
        self.grid.addWidget(QLabel("Audio"), 0, 2)
        self.grid.addWidget(QLabel("Controles"), 0, 3)

        self.rows = []
        # Inicialmente 10
        for _ in range(10):
            self._add_row()

        layout.addLayout(self.grid)

        # Botones para agregar/quitar filas
        row_controls = QHBoxLayout()
        self.add_row_btn = QPushButton("Agregar fila")
        self.remove_row_btn = QPushButton("Quitar última fila")
        row_controls.addWidget(self.add_row_btn)
        row_controls.addWidget(self.remove_row_btn)
        layout.addLayout(row_controls)

        self.apply_btn = QPushButton("Aplicar cambios")
        self.toggle_listen_btn = QPushButton("Iniciar escucha")
        layout.addWidget(self.apply_btn)
        layout.addWidget(self.toggle_listen_btn)

        self.setLayout(layout)

        # connections
        self.device_selector.currentIndexChanged.connect(self._on_device_changed)
        self.apply_btn.clicked.connect(self._apply_changes)
        self.toggle_listen_btn.clicked.connect(self._toggle_listening)

        # Señales por fila se conectan al crear fila
        self.add_row_btn.clicked.connect(self._add_row)
        self.remove_row_btn.clicked.connect(self._remove_last_row)

    def _wire_tray(self):
        self.tray = TrayController(self)
        self.tray.request_show.connect(self._on_tray_show)
        self.tray.request_start_listen.connect(self._start_listening)
        self.tray.request_stop_listen.connect(self._stop_listening)
        self.tray.request_quit.connect(self._on_tray_quit)
        self.tray.show()

    def _add_row(self):
        idx = len(self.rows)
        idx_label = QLabel(str(idx + 1))
        key_edit = QLineEdit()
        key_edit.setReadOnly(True)
        audio_edit = QLineEdit()
        audio_edit.setReadOnly(True)
        map_btn = QPushButton("Mapear")
        browse_btn = QPushButton("Seleccionar audio")

        self.grid.addWidget(idx_label, idx + 1, 0)
        self.grid.addWidget(key_edit, idx + 1, 1)
        self.grid.addWidget(audio_edit, idx + 1, 2)
        self.grid.addWidget(map_btn, idx + 1, 3)
        self.grid.addWidget(browse_btn, idx + 1, 4)

        row = {
            'idx_label': idx_label,
            'key_edit': key_edit,
            'audio_edit': audio_edit,
            'map_btn': map_btn,
            'browse_btn': browse_btn,
            'signature': None,
            'audio_path': None,
        }
        self.rows.append(row)

        map_btn.clicked.connect(lambda _, i=idx: self._map_row(i))
        browse_btn.clicked.connect(lambda _, i=idx: self._browse_audio(i))

    def _remove_last_row(self):
        if not self.rows:
            return
        row = self.rows.pop()
        # Remove widgets from grid and delete them
        for key in ['idx_label', 'key_edit', 'audio_edit', 'map_btn', 'browse_btn']:
            w = row.get(key)
            if w:
                self.grid.removeWidget(w)
                w.deleteLater()
        # Renumerar índices visibles
        for i, r in enumerate(self.rows):
            r['idx_label'].setText(str(i + 1))

    def closeEvent(self, event):
        # Minimize to tray instead of closing
        event.ignore()
        self.hide()
        self.tray.tray.showMessage(
            "Soundpad - Practica de libro by Aragon",
            "La app sigue ejecutándose en segundo plano.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def _on_tray_show(self):
        self.showNormal()
        self.activateWindow()

    def _on_tray_quit(self):
        try:
            if self.listener:
                self.listener.stop()
        finally:
            self.tray.hide()
            self.close()
            QApplication.instance().quit()

    def _populate_devices(self):
        self.device_selector.clear()
        self.device_map = []

        # Special option: All devices
        self.device_selector.addItem("Todos los dispositivos")
        self.device_map.append(("all", {}))

        # Global options
        self.device_selector.addItem("Global Keyboard")
        self.device_map.append(("keyboard", {}))
        self.device_selector.addItem("Global Mouse")
        self.device_map.append(("mouse", {}))

        # HID devices
        try:
            for dev in list_hid_devices():
                label = f"HID: {dev.vendor_name or 'Vendor'} {dev.product_name or 'Product'} (VID:{dev.vendor_id:04X} PID:{dev.product_id:04X})"
                self.device_selector.addItem(label)
                self.device_map.append(("hid", dev.__dict__))
        except Exception as e:
            QMessageBox.warning(self, "HID", f"No se pudieron listar dispositivos HID: {e}")

        # restore selection
        sel = self.config.data.get('selected_device', {"type": "keyboard"})
        for i, (t, info) in enumerate(self.device_map):
            if t == sel.get('type'):
                if t != 'hid' or (
                    info.get('vendor_id') == sel.get('vendor_id') and info.get('product_id') == sel.get('product_id')
                ):
                    self.device_selector.setCurrentIndex(i)
                    break

    def _on_device_changed(self, idx: int):
        # Settings will be applied on Apply
        pass

    def _browse_audio(self, row_idx: int):
        # Pause listening while browsing to avoid accidental triggers
        self._was_listening = self.listener.is_running if self.listener else False
        self._stop_listening()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecciona archivo de audio",
            filter="Audio Files (*.wav *.mp3 *.ogg *.flac);;All Files (*.*)",
        )
        if path:
            self.rows[row_idx]['audio_path'] = path
            self.rows[row_idx]['audio_edit'].setText(path)
        # Resume previous listening state without applying
        self._resume_listening_if_needed()

    def _map_row(self, row_idx: int):
        # Pause any current listening during capture
        self._was_listening = self.listener.is_running if self.listener else False
        self._stop_listening()

        dtype, dinfo = self.device_map[self.device_selector.currentIndex()]
        tmp_listener = MultiDeviceListener() if dtype == 'all' else DeviceListener(dtype, dinfo)
        # Keep a strong reference while capturing
        self._capture_listener = tmp_listener
        self.rows[row_idx]['key_edit'].setText("Escuchando...")
        # Disable map button to avoid multiple concurrent captures
        self.rows[row_idx]['map_btn'].setEnabled(False)

        def on_captured(sig: EventSignature):
            # Ensure the temporary listener stops (important for HID)
            try:
                tmp_listener.stop()
            except Exception:
                pass
            # Emit to main thread for UI update
            self.capture_ready.emit(row_idx, sig)

        tmp_listener.capture_next(on_captured)
        try:
            tmp_listener.start()
        except Exception as e:
            QMessageBox.critical(self, "Escucha", f"No se pudo iniciar escucha: {e}")
            self._capture_listener = None
            self.rows[row_idx]['map_btn'].setEnabled(True)
            return

        # Safety timeout: if nothing is captured within 8s, cancel capture
        def on_timeout():
            if self._capture_listener is tmp_listener:
                try:
                    tmp_listener.stop()
                except Exception:
                    pass
                self._capture_listener = None
                self.rows[row_idx]['key_edit'].setText("")
                self.rows[row_idx]['map_btn'].setEnabled(True)
                QMessageBox.information(self, "Mapeo", "No se detectó ninguna tecla/botón. Intenta de nuevo.")
            # Resume previous listening if it was active
            self._resume_listening_if_needed()
        QTimer.singleShot(8000, on_timeout)

    def _on_capture_ready(self, row_idx: int, sig: EventSignature):
        # Update UI with captured signature on main thread
        try:
            self.rows[row_idx]['signature'] = sig
            self.rows[row_idx]['key_edit'].setText(sig.human)
        except Exception:
            pass
        finally:
            self.rows[row_idx]['map_btn'].setEnabled(True)
            self._capture_listener = None
            # Resume previous listening state without applying new mappings yet
            self._resume_listening_if_needed()

    def _apply_changes(self):
        # stop existing listener
        if self.listener:
            self.listener.stop()
            self.listener = None

        # build mapping (signature + audio only)
        mapping = []
        for row in self.rows:
            sig = row['signature']
            path = row['audio_path']
            if sig and path:
                mapping.append({'signature': sig.to_dict(), 'audio': path})
        self.audio.preload([m['audio'] for m in mapping])

        dtype, dinfo = self.device_map[self.device_selector.currentIndex()]
        if dtype == 'all':
            self.listener = MultiDeviceListener()
        else:
            self.listener = DeviceListener(dtype, dinfo)
        for m in mapping:
            def make_cb(p):
                return lambda: self.audio.play(p)
            self.listener.bind(EventSignature.from_dict(m['signature']), make_cb(m['audio']))

        # save config
        self.config.data['selected_device'] = {'type': dtype, **dinfo}
        self.config.data['mappings'] = mapping
        self.config.save()

        # Auto-start listening after applying
        self._start_listening()
        QMessageBox.information(self, "Aplicado", "Mapeos aplicados y escucha iniciada.")

    def _start_listening(self):
        if not self.listener:
            self._apply_changes()
            return
        if self.listener and not self.listener.is_running:
            try:
                self.listener.start()
                self.toggle_listen_btn.setText("Detener escucha")
            except Exception as e:
                QMessageBox.critical(self, "Escucha", f"No se pudo iniciar: {e}")

    def _stop_listening(self):
        if self.listener and self.listener.is_running:
            self.listener.stop()
            self.toggle_listen_btn.setText("Iniciar escucha")
        # Stop any currently playing sounds when stopping listening
        try:
            self.audio.stop_all()
        except Exception:
            pass

    def _resume_listening_if_needed(self):
        # Resume only if there was an active listener before the temporary pause
        if self._was_listening and self.listener and not self.listener.is_running:
            try:
                self.listener.start()
                self.toggle_listen_btn.setText("Detener escucha")
            except Exception:
                pass
        self._was_listening = False

    def _toggle_listening(self):
        if self.listener and self.listener.is_running:
            self._stop_listening()
        else:
            self._start_listening()

    def _load_config(self):
        data = self.config.data
        # restore mappings
        rows = data.get('mappings', [])
        # Ensure enough rows exist
        while len(self.rows) < len(rows):
            self._add_row()
        for i, item in enumerate(rows):
            try:
                sig = EventSignature.from_dict(item['signature'])
                self.rows[i]['signature'] = sig
                self.rows[i]['key_edit'].setText(sig.human)
                audio_val = item.get('audio', '')
                self.rows[i]['audio_path'] = audio_val
                if self.rows[i].get('audio_edit'):
                    self.rows[i]['audio_edit'].setText(audio_val)
            except Exception:
                pass
