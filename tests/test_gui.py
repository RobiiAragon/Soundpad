"""Offscreen smoke test of the main window: add rows, capture, apply, reload."""
import json

import pytest

pytest.importorskip("PyQt6.QtWidgets")
pytest.importorskip("pygame")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from src.core.types import EventSignature  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    app = QApplication.instance() or QApplication([])
    from src.gui.main_window import MainWindow
    w = MainWindow()
    yield w
    if w.listener:
        w.listener.stop()
    w.tray.hide()


def test_capture_apply_and_reload(window, tmp_path, monkeypatch):
    w = window
    w._add_row(); w._add_row()
    item = w.mapping_manager.get_by_row(0)
    item.audio = str(tmp_path / "missing.wav")
    # Simulate a finished capture coming back through the queued signal.
    w._capture_listener = object()
    w._on_capture_ready(0, EventSignature(type="keyboard", code="ctrl+k", human="Combo Ctrl+K"))
    assert w.table.item(0, 1).text() == "Combo Ctrl+K"
    # A late result after the timeout must be ignored.
    w._on_capture_ready(1, EventSignature(type="keyboard", code="z", human="Tecla Z"))
    assert w.mapping_manager.get_by_row(1).signature is None

    monkeypatch.setattr(w, "_start_listening", lambda: None)
    w.volume_slider.setValue(40)
    w._save_volume()
    w._apply_changes()

    saved = json.loads((tmp_path / "USB-Sound-Mapper" / "config.json").read_text(encoding="utf-8"))
    assert [m["id"] for m in saved["mappings"]] == [1, 2]
    assert saved["volume"] == 0.4

    w.mapping_manager.load(saved["mappings"])
    assert w.mapping_manager.get_by_row(0).signature.code == "ctrl+k"


def test_tray_menu_has_stop_sounds(window):
    texts = [a.text() for a in window.tray.menu.actions()]
    assert "Detener sonidos" in texts
