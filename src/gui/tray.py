from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtCore import pyqtSignal, QObject


class TrayController(QObject):
    request_show = pyqtSignal()
    request_quit = pyqtSignal()
    request_start_listen = pyqtSignal()
    request_stop_listen = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tray = QSystemTrayIcon(QIcon())
        self.tray.setToolTip("USB Sound Mapper")
        menu = QMenu()

        self.show_action = QAction("Mostrar ventana")
        self.start_action = QAction("Iniciar escucha")
        self.stop_action = QAction("Detener escucha")
        self.quit_action = QAction("Salir")

        menu.addAction(self.show_action)
        menu.addAction(self.start_action)
        menu.addAction(self.stop_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)

        self.tray.setContextMenu(menu)

        self.show_action.triggered.connect(self.request_show)
        self.start_action.triggered.connect(self.request_start_listen)
        self.stop_action.triggered.connect(self.request_stop_listen)
        self.quit_action.triggered.connect(self.request_quit)

    def show(self):
        self.tray.show()

    def hide(self):
        self.tray.hide()
