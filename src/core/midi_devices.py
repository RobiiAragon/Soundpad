from dataclasses import dataclass
from typing import List

try:
    import mido
except Exception:  # pragma: no cover
    mido = None


@dataclass
class MidiDeviceInfo:
    name: str


def list_midi_inputs() -> List[MidiDeviceInfo]:
    devices: List[MidiDeviceInfo] = []
    if not mido:
        return devices
    try:
        for name in mido.get_input_names():
            devices.append(MidiDeviceInfo(name=name))
    except Exception:
        return devices
    return devices
