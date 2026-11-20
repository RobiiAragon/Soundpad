import json
import math
import struct
import wave

import pytest

from src.core.config_store import ConfigStore
from src.core.device_listener import MultiDeviceListener
from src.core.mapping_manager import MappingManager
from src.core.types import EventSignature


def sig(t="keyboard", code="a", **kw):
    return EventSignature(type=t, code=code, human=code, **kw)


# ---- config ----

def test_config_roundtrip(tmp_path):
    c = ConfigStore(str(tmp_path))
    c.data["mappings"] = [{"id": 1, "signature": sig().to_dict(), "audio": "x.wav"}]
    assert c.save()
    assert ConfigStore(str(tmp_path)).data["mappings"] == c.data["mappings"]
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("content", ["{not json", "[]", '{"mappings": 5, "selected_device": "x"}'])
def test_config_ignores_bad_files(tmp_path, content):
    (tmp_path / "config.json").write_text(content, encoding="utf-8")
    c = ConfigStore(str(tmp_path))
    assert c.data["mappings"] == []
    assert c.data["selected_device"] == {"type": "keyboard"}


# ---- mappings ----

def test_legacy_mappings_without_ids_get_unique_ids():
    # Configs written before ids were saved: removing one row used to remove all of them.
    m = MappingManager()
    m.load([{"signature": sig(code="a").to_dict(), "audio": "a.wav"},
            {"signature": sig(code="b").to_dict(), "audio": "b.wav"}])
    ids = [i.id for i in m.items()]
    assert len(set(ids)) == 2 and min(ids) > 0
    m.remove_ids([ids[-1]])
    assert [i.audio for i in m.items()] == ["a.wav"]
    assert m.add().id not in ids[:1]


def test_duplicate_ids_are_reassigned_and_bad_rows_skipped():
    m = MappingManager()
    m.load([{"id": 3, "audio": "a"}, {"id": 3, "audio": "b"},
            {"id": 4, "signature": {"type": "bogus"}}, {"id": 5, "signature": {"code": "x"}}])
    assert [i.audio for i in m.items()] == ["a", "b"]
    assert len({i.id for i in m.items()}) == 2


def test_serialize_roundtrip_keeps_incomplete_rows():
    m = MappingManager()
    a = m.add(); a.signature = sig(code="ctrl+a"); a.audio = "a.wav"
    m.add()  # empty row
    m2 = MappingManager(); m2.load(m.serialize())
    assert m2.serialize() == m.serialize()


def test_detect_duplicates():
    m = MappingManager()
    for _ in range(2):
        it = m.add(); it.signature = sig(code="x")
    other = m.add(); other.signature = sig(code="y")
    dups = m.detect_duplicates()
    assert list(dups) == ["keyboard:None:None:x"]


# ---- multi-device combos ----

def test_multi_device_combo_fires_once_for_two_device_types():
    md = MultiDeviceListener()
    fired = []
    md.bind(EventSignature(type="multi", code="kb:a+ms:left"), lambda: fired.append(1))
    md._on_raw_event(sig("keyboard", "a"))
    assert fired == []  # one device type is not a multi combo
    md._on_raw_event(sig("mouse", "left"))
    md._on_raw_event(sig("mouse", "left"))
    assert fired == [1]


def test_multi_device_combo_expires():
    md = MultiDeviceListener()
    fired = []
    md.bind(EventSignature(type="multi", code="kb:a+ms:left"), lambda: fired.append(1))
    md._on_raw_event(sig("keyboard", "a"))
    md._md_last_time -= 10  # simulate a long pause
    md._on_raw_event(sig("mouse", "left"))
    assert fired == []


# ---- audio ----

def _tone(path, seconds=0.2, rate=22050):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 10)))
                               for i in range(int(rate * seconds))))


def test_audio_player_volume_and_bad_files(tmp_path):
    pytest.importorskip("pygame")
    from src.core.audio_player import AudioPlayer
    good = tmp_path / "t.wav"; _tone(good)
    bad = tmp_path / "bad.wav"; bad.write_bytes(b"nope")
    p = AudioPlayer(max_channels=8)
    p.preload([str(good), str(bad)])
    assert list(p.cache) == [str(good)]
    p.set_volume(0.25)
    assert abs(p.cache[str(good)].get_volume() - 0.25) < 0.01
    p.set_volume(7)
    assert p.volume == 1.0
    p.play(str(good)); p.play(str(bad)); p.play("")
    p.stop_all()
