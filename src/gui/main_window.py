from PyQt6.QtWidgets import (
    QApplication,
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QFileDialog, QGridLayout,
    QLineEdit, QMessageBox, QSystemTrayIcon
)
from PyQt6.QtCore import Qt, QTimer

from src.core.config_store import ConfigStore
from src.core.audio_player import AudioPlayer
from src.core.device_listener import DeviceListener
from src.core.types import EventSignature
from src.core.hid_devices import list_hid_devices, HidDeviceInfo
from .tray import TrayController


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("USB Sound Mapper")
        self.resize(720, 520)

        self.config = ConfigStore()
        self.audio = AudioPlayer()
        self.listener = None  # type: DeviceListener | None

        self.device_map = []  # list[tuple[str, dict]]

        self._build_ui()
        self._load_config()
        self._populate_devices()
        self._wire_tray()

    def _build_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Selecciona dispositivo (HID/Global)"))
        self.device_selector = QComboBox()
        layout.addWidget(self.device_selector)

        grid = QGridLayout()
        grid.addWidget(QLabel("#"), 0, 0)
        grid.addWidget(QLabel("Botón/Tecla asignada"), 0, 1)
        grid.addWidget(QLabel("Audio"), 0, 2)
        grid.addWidget(QLabel("Acciones"), 0, 3)

        self.rows = []
        for i in range(10):
            idx_label = QLabel(str(i+1))
            key_edit = QLineEdit()
            key_edit.setReadOnly(True)
            audio_edit = QLineEdit()
            audio_edit.setReadOnly(True)
            map_btn = QPushButton("Mapear")
            browse_btn = QPushButton("Seleccionar audio")

            grid.addWidget(idx_label, i+1, 0)
            grid.addWidget(key_edit, i+1, 1)
            grid.addWidget(audio_edit, i+1, 2)
            grid.addWidget(map_btn, i+1, 3)
            grid.addWidget(browse_btn, i+1, 4)

            self.rows.append({
                'key_edit': key_edit,
                'audio_edit': audio_edit,
                'map_btn': map_btn,
                'browse_btn': browse_btn,
                'signature': None,  # EventSignature
                'audio_path': None,
            })

        layout.addLayout(grid)

        self.apply_btn = QPushButton("Aplicar cambios")
        self.toggle_listen_btn = QPushButton("Iniciar escucha")
        layout.addWidget(self.apply_btn)
        layout.addWidget(self.toggle_listen_btn)

        self.setLayout(layout)

        # connections
        self.device_selector.currentIndexChanged.connect(self._on_device_changed)
        self.apply_btn.clicked.connect(self._apply_changes)
        self.toggle_listen_btn.clicked.connect(self._toggle_listening)

        for idx, row in enumerate(self.rows):
            row['map_btn'].clicked.connect(lambda _, i=idx: self._map_row(i))
            row['browse_btn'].clicked.connect(lambda _, i=idx: self._browse_audio(i))

    def _wire_tray(self):
        self.tray = TrayController(self)
    self.tray.request_show.connect(self._on_tray_show)
    self.tray.request_start_listen.connect(self._start_listening)
    self.tray.request_stop_listen.connect(self._stop_listening)
    self.tray.request_quit.connect(self._on_tray_quit)
    self.tray.show()

    def closeEvent(self, event):
        # Minimize to tray instead of closing
        event.ignore()
        self.hide()
        self.tray.tray.showMessage("USB Sound Mapper", "La app sigue ejecutándose en segundo plano.", QSystemTrayIcon.MessageIcon.Information, 3000)

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
                if t != 'hid' or (info.get('vendor_id') == sel.get('vendor_id') and info.get('product_id') == sel.get('product_id')):
                    self.device_selector.setCurrentIndex(i)
                    break

    def _on_device_changed(self, idx: int):
        # nothing special; will apply on Apply
        pass

    def _browse_audio(self, row_idx: int):
        # Pause listening while browsing to avoid accidental triggers
        self._stop_listening()
        path, _ = QFileDialog.getOpenFileName(self, "Selecciona archivo de audio", filter="Audio Files (*.wav *.mp3 *.ogg *.flac);;All Files (*.*)")
        if path:
            self.rows[row_idx]['audio_path'] = path
            self.rows[row_idx]['audio_edit'].setText(path)
        # Optionally resume listening
        # self._start_listening()

    def _map_row(self, row_idx: int):
        # Pause any current listening during capture
        self._stop_listening()
        # start a temporary listener for capture
        dtype, dinfo = self.device_map[self.device_selector.currentIndex()]
        tmp_listener = DeviceListener(dtype, dinfo)
        try:
            tmp_listener.start()
        except Exception as e:
            QMessageBox.critical(self, "Escucha", f"No se pudo iniciar escucha: {e}")
            return

        self.rows[row_idx]['key_edit'].setText("Escuchando...")

        def on_captured(sig: EventSignature):
            tmp_listener.stop()
            self.rows[row_idx]['signature'] = sig
            self.rows[row_idx]['key_edit'].setText(sig.human)
            # Resume listening if mappings are active
            self._start_listening()

        tmp_listener.capture_next(on_captured)

    def _apply_changes(self):
        # stop existing listener
        if self.listener:
            self.listener.stop()
            self.listener = None

        # build mapping
        mapping = []
        for row in self.rows:
            sig = row['signature']
            path = row['audio_path']
            if sig and path:
                mapping.append({'signature': sig.to_dict(), 'audio': path})
        self.audio.preload([m['audio'] for m in mapping])

        dtype, dinfo = self.device_map[self.device_selector.currentIndex()]
        self.listener = DeviceListener(dtype, dinfo)
        for m in mapping:
            def make_cb(audio_path):
                return lambda: self.audio.play(audio_path)
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

    def _toggle_listening(self):
        if self.listener and self.listener.is_running:
            self._stop_listening()
        else:
            self._start_listening()

    def _load_config(self):
        data = self.config.data
        # restore mappings
        rows = data.get('mappings', [])
        for i, item in enumerate(rows[:10]):
            try:
                sig = EventSignature.from_dict(item['signature'])
                self.rows[i]['signature'] = sig
                self.rows[i]['key_edit'].setText(sig.human)
                self.rows[i]['audio_path'] = item.get('audio')
                self.rows[i]['audio_edit'].setText(item.get('audio', ''))
            except Exception:
                pass
