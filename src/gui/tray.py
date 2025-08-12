from PyQt6.QtGui import QIcon, QAction, QPainter, QColor, QPixmap, QFont
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtCore import pyqtSignal, QObject, Qt


class TrayController(QObject):
    request_show = pyqtSignal()
    request_quit = pyqtSignal()
    request_start_listen = pyqtSignal()
    request_stop_listen = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Build a simple in-memory icon so Windows shows it in the tray
        pix = QPixmap(32, 32)
        pix.fill(QColor(30, 144, 255))  # DodgerBlue
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.GlobalColor.white)
        font = QFont()
        font.setBold(True)
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "SP")
        painter.end()

        self.tray = QSystemTrayIcon(QIcon(pix))
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
