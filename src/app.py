from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow
import sys
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimized", action="store_true", help="Start minimized to tray")
    args, _ = parser.parse_known_args()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep running in tray
    app.setApplicationName("USB Sound Mapper")
    window = MainWindow()
    if args.minimized:
        window.hide()
    else:
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
