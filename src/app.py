from PyQt6.QtWidgets import QApplication
import sys, os

# --- Dynamic import of MainWindow with multiple fallbacks for PyInstaller builds ---
# When building without using the provided .spec (e.g. running `pyinstaller src/app.py`),
# hidden imports and the package path may not be correctly resolved. We proactively
# adjust sys.path and attempt several import strategies so the app still launches.
def _import_main_window():
    attempted = []
    # 1) Direct expected import (development + spec build)
    try:
        from src.gui.main_window import MainWindow  # type: ignore
        return MainWindow
    except ModuleNotFoundError as e:  # pragma: no cover - only in frozen fallback
        attempted.append(f"src.gui.main_window -> {e}")
    # 2) If running frozen, add potential base / src paths then retry
    base_candidates = []
    try:
        if getattr(sys, 'frozen', False):  # PyInstaller
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            base_candidates.append(base_dir)
            base_candidates.append(os.path.join(base_dir, 'src'))
    except Exception:
        pass
    # Always also consider directory containing this file (dev environment)
    this_dir = os.path.dirname(__file__)
    base_candidates.append(os.path.dirname(this_dir))  # project root
    base_candidates.append(os.path.join(os.path.dirname(this_dir), 'src'))
    for p in base_candidates:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    try:
        from src.gui.main_window import MainWindow  # type: ignore
        return MainWindow
    except ModuleNotFoundError as e:  # pragma: no cover
        attempted.append(f"(after path adjust) src.gui.main_window -> {e}")
    # 3) Flattened layout: modules without leading 'src.'
    try:
        from gui.main_window import MainWindow  # type: ignore
        return MainWindow
    except ModuleNotFoundError as e:  # pragma: no cover
        attempted.append(f"gui.main_window -> {e}")
    # 4) Final: give detailed error to help user build with spec
    raise ModuleNotFoundError(
        "No se pudo importar MainWindow. Intenta reconstruir usando el archivo .spec. Intentos: "
        + " | ".join(attempted)
    )

MainWindow = _import_main_window()
import argparse


def main():
    # Hook global para registrar crashes en crash.log
    import traceback
    def _excepthook(t, v, tb):
        try:
            with open('crash.log', 'a', encoding='utf-8') as f:
                f.write('\n=== Unhandled Exception ===\n')
                traceback.print_exception(t, v, tb, file=f)
        except Exception:
            pass
        traceback.print_exception(t, v, tb)
    sys.excepthook = _excepthook
    # Global crash hook para registrar errores en entorno PyInstaller sin consola
    import traceback
    def _excepthook(t, v, tb):
        try:
            with open('crash.log', 'a', encoding='utf-8') as f:
                f.write('\n=== Unhandled Exception ===\n')
                traceback.print_exception(t, v, tb, file=f)
        except Exception:
            pass
        # También imprimir a stdout (si existe consola)
        traceback.print_exception(t, v, tb)
    sys.excepthook = _excepthook
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimized", action="store_true", help="Start minimized to tray")
    args, _ = parser.parse_known_args()

    # Adjust CWD to executable dir (PyInstaller) so relative paths (config, audio) work
    try:
        if getattr(sys, 'frozen', False):
            os.chdir(os.path.dirname(sys.executable))
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep running in tray
    app.setApplicationName("Soundpad v1.0.1 - by Aragón")
    window = MainWindow()
    if args.minimized:
        window.hide()
    else:
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
