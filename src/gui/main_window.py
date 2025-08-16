from PyQt6.QtWidgets import (
    QApplication,
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QFileDialog,
    QLineEdit, QMessageBox, QSystemTrayIcon, QHBoxLayout, QCheckBox,
    QTabWidget, QTextEdit, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QStyle, QToolButton, QMenu
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QCursor  # (usar en futuro si se necesita; QIcon eliminado)

from src.core.config_store import ConfigStore
from src.core.audio_player import AudioPlayer
from src.core.device_listener import DeviceListener, MultiDeviceListener
from src.core.types import EventSignature
from src.core.hid_devices import list_hid_devices
from .tray import TrayController
from src.core.logger import log, has_listeners
from src.core.mapping_manager import MappingManager, MappingItem


class _LogBridge(QObject):
    line = pyqtSignal(str)



class MainWindow(QWidget):
    capture_ready = pyqtSignal(int, object)  # (row_idx, EventSignature)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Soundpad - Practica de libro by Aragon")
        self.resize(880, 560)

        # state
        self.config = ConfigStore()
        self.audio = AudioPlayer()
        self.listener = None
        self._was_listening = False
        self._capture_listener = None
        self.device_map = []

        # ui and wiring
        self._build_ui()
        self._apply_styles()
        self._load_config()
        self._populate_devices()
        self._wire_tray()
        self.capture_ready.connect(self._on_capture_ready)

    def _build_ui(self):
        # Delegar a helper estable para evitar problemas de indentación
        self._init_ui_core()

    def _init_ui_core(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Selecciona dispositivo (HID/Global)"))
        self.device_selector = QComboBox()
        device_row = QHBoxLayout()
        device_row.addWidget(self.device_selector)
        self.refresh_devices_btn = QPushButton("Refrescar dispositivos")
        self.log_chk = QCheckBox("Log")
        device_row.addWidget(self.refresh_devices_btn)
        device_row.addWidget(self.log_chk)
        device_row.addStretch(1)
        layout.addLayout(device_row)

        self.mapping_manager = MappingManager()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Evento", "Audio", "Acciones"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        row_controls = QHBoxLayout()
        self.add_row_btn = QPushButton("Añadir")
        self.remove_row_btn = QPushButton("Eliminar")
        self.dup_btn = QPushButton("Duplicados")
        row_controls.addWidget(self.add_row_btn)
        row_controls.addWidget(self.remove_row_btn)
        row_controls.addWidget(self.dup_btn)
        row_controls.addStretch(1)
        layout.addLayout(row_controls)

        self.apply_btn = QPushButton("Aplicar / Reiniciar escucha")
        self.toggle_listen_btn = QPushButton("Iniciar escucha")
        layout.addWidget(self.apply_btn)
        layout.addWidget(self.toggle_listen_btn)

        self.device_selector.currentIndexChanged.connect(self._on_device_changed)
        self.apply_btn.clicked.connect(self._apply_changes)
        self.toggle_listen_btn.clicked.connect(self._toggle_listening)
        self.add_row_btn.clicked.connect(self._add_row)
        self.remove_row_btn.clicked.connect(self._remove_selected_row)
        self.dup_btn.clicked.connect(self._show_duplicates)
        self.refresh_devices_btn.clicked.connect(self._populate_devices)
        self.log_chk.stateChanged.connect(self._on_log_toggle)

        self.tabs = QTabWidget()
        self.main_tab = QWidget(); self.main_tab.setLayout(layout)
        self.log_view = QTextEdit(); self.log_view.setReadOnly(True)
        self.tabs.addTab(self.main_tab, "Principal")
        self.tabs.addTab(self.log_view, "Log")
        outer = QVBoxLayout(); outer.addWidget(self.tabs)
        self.status_lbl = QLineEdit(); self.status_lbl.setReadOnly(True); self.status_lbl.setPlaceholderText("Listo")
        outer.addWidget(self.status_lbl)
        self.setLayout(outer)

    # Selección desactivada: no se normalizan colores

    def _apply_styles(self):
        # Simple dark theme to ensure text contrast (labels/items were blending)
        style = """
QWidget { font-size: 11px; }
QTableWidget {
    background: #202225;
    alternate-background-color: #26292c;
    color: #223040; /* texto normal oscuro azulado */
    gridline-color: #404449;
    selection-background-color: #3d5a80;
    selection-color: #ffffff; /* texto seleccionado blanco */
}
QTableWidget::item { color: #223040; }
QTableWidget::item:selected { color: #ffffff; }
QHeaderView::section {
    background: #2c2f33;
    color: #dddddd;
    padding: 4px;
    border: 0px solid #444;
    border-right: 1px solid #444;
}
QToolButton, QPushButton {
    background: #3a3d41;
    color: #e6e6e6;
    border: 1px solid #505458;
    padding: 2px 6px;
    border-radius: 3px;
}
QToolButton:hover, QPushButton:hover {
    background: #4a4e52;
}
QLineEdit[readOnly="true"] { background: #2c2f33; color: #bbbbbb; }
QTabWidget::pane { border: 1px solid #444; }
QTabBar::tab { background: #2c2f33; padding: 4px 10px; }
QTabBar::tab:selected { background: #3a3d41; }
        """
        self.setStyleSheet(style)

    def _on_log_toggle(self, _):
        import os
        from src.core import logger
        if self.log_chk.isChecked():
            # Enable MIDI + HID debug env flags so listener prints become structured logs
            os.environ['SP_DEBUG_HID'] = '1'
            # Register UI sink
            if not hasattr(self, '_log_bridge'):
                self._log_bridge = _LogBridge()
                self._log_bridge.line.connect(self.log_view.append)
            def sink(line: str):
                try:
                    # simple overflow control
                    if self.log_view.document().blockCount() > 4800:
                        self.log_view.clear()
                        self.log_view.append('[log] limpiado por overflow')
                    self._log_bridge.line.emit(line)
                except Exception:
                    pass
            self._log_sink = sink
            logger.register(self._log_sink)
            logger.log('Logging habilitado')
            self.tabs.setCurrentWidget(self.log_view)
        else:
            if hasattr(self, '_log_sink'):
                try:
                    from src.core import logger
                    logger.unregister(self._log_sink)
                except Exception:
                    pass
                del self._log_sink
            for k in ['SP_DEBUG_HID']:
                if k in os.environ:
                    del os.environ[k]

    def _wire_tray(self):
        self.tray = TrayController(self)
        self.tray.request_show.connect(self._on_tray_show)
        self.tray.request_start_listen.connect(self._start_listening)
        self.tray.request_stop_listen.connect(self._stop_listening)
        self.tray.request_quit.connect(self._on_tray_quit)
        self.tray.show()

    def _add_row(self):
        item = self.mapping_manager.add()
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._refresh_row(row, item)

    def _refresh_row(self, row: int, item: MappingItem):
        # Wrapper to avoid indentation issues in original method body
        self._do_refresh_row(row, item)

    def _do_refresh_row(self, row: int, item: MappingItem): self._build_row(row, item)

    def _build_row(self, row: int, item: MappingItem):
        # Wrapper interno que delega a función global para evitar errores de indentación en build
        build_row(self, row, item)

    def _ensure_action_widgets(self, row: int):
        if self.table.cellWidget(row, 3) is not None:
            return
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        buttons = []
        map_btn = QToolButton(); map_btn.setText("Capturar"); buttons.append(map_btn)
        browse_btn = QToolButton(); browse_btn.setText("Audio"); buttons.append(browse_btn)
        play_btn = QToolButton(); play_btn.setText("▶"); buttons.append(play_btn)
        clear_btn = QToolButton(); clear_btn.setText("Limpiar"); buttons.append(clear_btn)
        for b in buttons:
            layout.addWidget(b)
        layout.addStretch(1)
        self.table.setCellWidget(row, 3, container)
        map_btn.clicked.connect(lambda _, r=row: self._map_row(r))
        browse_btn.clicked.connect(lambda _, r=row: self._browse_audio(r))
        clear_btn.clicked.connect(lambda _, r=row: self._clear_row(r))
        play_btn.clicked.connect(lambda _, r=row: self._preview_audio(r))

    def _clear_row(self, row: int):
        item = self.mapping_manager.get_by_row(row)
        if not item: return
        item.signature = None
        item.audio = ''
        self._refresh_row(row, item)
        self._update_duplicate_highlight()

    def _preview_audio(self, row: int):
        item = self.mapping_manager.get_by_row(row)
        if item and item.audio:
            self.audio.play(item.audio)
            self._set_status(f"Reproduciendo preview fila {row+1}")

    def _remove_selected_row(self):
        # Con selección desactivada, tomamos la última fila como objetivo
        if self.table.selectionMode() == QAbstractItemView.SelectionMode.NoSelection:
            row = self.table.rowCount() - 1
        else:
            row = self.table.currentRow()
        if row < 0:
            return
        item = self.mapping_manager.get_by_row(row)
        if not item:
            return
        self.mapping_manager.remove_ids([item.id])
        self.table.removeRow(row)
        # Renumber
        for r in range(self.table.rowCount()):
            if self.table.item(r,0):
                self.table.item(r,0).setText(str(r+1))
        self._update_duplicate_highlight()

    def _show_duplicates(self):
        dups = self.mapping_manager.detect_duplicates()
        if not dups:
            QMessageBox.information(self, "Duplicados", "No hay duplicados.")
            return
        msg = []
        for k, lst in dups.items():
            codes = ', '.join(str(i.id) for i in lst)
            msg.append(f"{k} -> filas {codes}")
        QMessageBox.warning(self, "Duplicados", "Se encontraron duplicados:\n" + '\n'.join(msg))
        self._update_duplicate_highlight()

    def _update_duplicate_highlight(self):
        dups = self.mapping_manager.detect_duplicates()
        dup_ids = {i.id for lst in dups.values() for i in lst}
        for r in range(self.table.rowCount()):
            item = self.mapping_manager.get_by_row(r)
            base_color = Qt.GlobalColor.white
            if item and item.id in dup_ids:
                base_color = Qt.GlobalColor.yellow
            for c in range(0,3):
                it = self.table.item(r,c)
                if it:
                    it.setBackground(base_color)

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
        if has_listeners():
            log('Dispositivos: refrescando listado')
        self.device_selector.clear()
        self.device_map = []

        # Special option: All devices
        self.device_selector.addItem("Todos los dispositivos")
        self.device_map.append(("all", {}))
        if has_listeners():
            log('Añadido alias Todos los dispositivos')

        # Global options
        self.device_selector.addItem("Global Keyboard")
        self.device_map.append(("keyboard", {}))
        self.device_selector.addItem("Global Mouse")
        self.device_map.append(("mouse", {}))
        if has_listeners():
            log('Añadidos global keyboard/mouse')

        # HID devices (deduplicados por VID:PID en list_hid_devices)
        try:
            hid_list = list_hid_devices()
            for dev in hid_list:
                label = f"HID: {dev.vendor_name or 'Vendor'} {dev.product_name or 'Product'} (VID:{dev.vendor_id:04X} PID:{dev.product_id:04X})"
                self.device_selector.addItem(label)
                self.device_map.append(("hid", dev.__dict__))
                if has_listeners():
                    log(f"HID detectado {label}")
        except Exception as e:
            QMessageBox.warning(self, "HID", f"No se pudieron listar dispositivos HID: {e}")

        # MIDI eliminado

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
        if 0 <= idx < len(self.device_map):
            dtype, _ = self.device_map[idx]
            if has_listeners():
                log(f"Dispositivo seleccionado idx={idx} tipo={dtype}")
        else:
            if has_listeners():
                log(f"Dispositivo seleccionado inválido idx={idx}")

    def _browse_audio(self, row_idx: int):
        self._was_listening = self.listener.is_running if self.listener else False
        self._stop_listening()
        path, _ = QFileDialog.getOpenFileName(self, "Selecciona archivo de audio", filter="Audio Files (*.wav *.mp3 *.ogg *.flac);;All Files (*.*)")
        if path:
            item = self.mapping_manager.get_by_row(row_idx)
            if item:
                item.audio = path
                self._refresh_row(row_idx, item)
                self._update_duplicate_highlight()
        self._resume_listening_if_needed()

    def _map_row(self, row_idx: int):
        self._was_listening = self.listener.is_running if self.listener else False
        self._stop_listening()
        item = self.mapping_manager.get_by_row(row_idx)
        if not item:
            return
        dtype, dinfo = self.device_map[self.device_selector.currentIndex()]
        tmp_listener = MultiDeviceListener() if dtype == 'all' else DeviceListener(dtype, dinfo)
        self._capture_listener = tmp_listener
        self._set_status(f"Capturando fila {row_idx+1}... presiona combinación")
        def on_captured(sig: EventSignature):
            try:
                tmp_listener.stop()
            except Exception:
                pass
            item.signature = sig
            self._refresh_row(row_idx, item)
            self._update_duplicate_highlight()
            self._capture_listener = None
            self._set_status(f"Captura fila {row_idx+1}: {sig.human}")
            self._resume_listening_if_needed()
            if has_listeners():
                log(f"Captura completada fila={row_idx+1} sig={sig.type}:{sig.code}")
        tmp_listener.capture_next(on_captured)
        try:
            tmp_listener.start()
        except Exception as e:
            QMessageBox.critical(self, "Captura", f"No se pudo iniciar: {e}")
            self._capture_listener = None
            self._resume_listening_if_needed()
            return
        def on_timeout():
            if self._capture_listener is tmp_listener:
                try:
                    tmp_listener.stop()
                except Exception:
                    pass
                self._capture_listener = None
                self._set_status("Captura cancelada (timeout)")
                QMessageBox.information(self, "Captura", "No se detectó ninguna entrada.")
                self._resume_listening_if_needed()
        QTimer.singleShot(8000, on_timeout)

    def _on_capture_ready(self, row_idx: int, sig: EventSignature):
        # Legacy (no-op with new table approach)
        pass

    def _apply_changes(self):
        # stop existing listener
        if self.listener:
            self.listener.stop()
            self.listener = None

        # build mapping (signature + audio only)
        mapping = []
        for m in self.mapping_manager.items():
            if m.signature and m.audio:
                mapping.append({'signature': m.signature.to_dict(), 'audio': m.audio})
        self.audio.preload([m['audio'] for m in mapping])

        dtype, dinfo = self.device_map[self.device_selector.currentIndex()]
        if dtype == 'all':
            self.listener = MultiDeviceListener()
        else:
            self.listener = DeviceListener(dtype, dinfo)
        for m in mapping:
            sig = EventSignature.from_dict(m['signature'])
            audio_path = m['audio']
            self.listener.bind(sig, lambda p=audio_path: self.audio.play(p))

        # save config
        self.config.data['selected_device'] = {'type': dtype, **dinfo}
        self.config.data['mappings'] = mapping
        self.config.save()

        # Auto-start listening after applying
        self._start_listening()
        QMessageBox.information(self, "Aplicado", "Mapeos aplicados y escucha iniciada.")
        # Log action
        try:
            from src.core.logger import log
            log('Mapeos aplicados y escucha iniciada')
        except Exception:
            pass

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
        rows = data.get('mappings', [])
        self.mapping_manager.load(rows)
        self.table.setRowCount(0)
        for item in self.mapping_manager.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._refresh_row(r, item)
        self._update_duplicate_highlight()
    # MIDI opciones eliminadas

    # _current_midi_options removido

    def _set_status(self, msg: str):
        if has_listeners():
            log(msg)
        # Optional: could add a status bar later
        try:
            if hasattr(self, 'status_lbl'):
                self.status_lbl.setText(msg)
        except Exception:
            pass

# --- Función helper fuera de la clase (evita problemas de indentación en pyinstaller) ---
def build_row(win: MainWindow, row: int, item: MappingItem):
    # Column 0: index
    idx_item = QTableWidgetItem(str(row + 1))
    idx_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    win.table.setItem(row, 0, idx_item)

    # Column 1: event signature
    ev_text = item.signature.human if item.signature else "<sin evento>"
    ev_item = QTableWidgetItem(ev_text)
    ev_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    ev_item.setToolTip(ev_text)
    win.table.setItem(row, 1, ev_item)

    # Column 2: audio path
    audio_text = item.audio if item.audio else "<sin audio>"
    audio_item = QTableWidgetItem(audio_text)
    audio_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    audio_item.setToolTip(audio_text)
    win.table.setItem(row, 2, audio_item)

    # Column 3: ensure action buttons
    win._ensure_action_widgets(row)
    # Selección desactivada: nada adicional
