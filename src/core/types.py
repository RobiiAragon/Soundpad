from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any


@dataclass
class EventSignature:
    type: Literal['hid', 'keyboard', 'mouse', 'multi', 'midi']
    # For HID: vendor_id, product_id, and raw pattern (hex string)
    # For MIDI: code = '<msg_type>:<channel>:<note/control>', e.g. 'note_on:1:60'
    vendor_id: Optional[int] = None
    product_id: Optional[int] = None
    code: str = ''  # normalized string payload (for MIDI: msg_type:channel:note/control)
    human: str = ''  # human-readable label (for MIDI: e.g. 'MIDI Note On C4 (ch 1)')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'vendor_id': self.vendor_id,
            'product_id': self.product_id,
            'code': self.code,
            'human': self.human,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> 'EventSignature':
        return EventSignature(
            type=d['type'],
            vendor_id=d.get('vendor_id'),
            product_id=d.get('product_id'),
            code=d.get('code', ''),
            human=d.get('human', ''),
        )
