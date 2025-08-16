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
        seen = set()
        for raw_name in mido.get_input_names():
            # Normalizar nombre para deduplicar (quitar espacios repetidos y mayúsculas)
            norm = ' '.join(raw_name.strip().split()).lower()
            if norm in seen:
                continue
            seen.add(norm)
            devices.append(MidiDeviceInfo(name=raw_name))
    except Exception:
        return devices
    return devices
