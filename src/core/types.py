from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any


@dataclass
class EventSignature:
    type: Literal['hid', 'keyboard', 'mouse']
    # For HID: vendor_id, product_id, and raw pattern (hex string)
    vendor_id: Optional[int] = None
    product_id: Optional[int] = None
    code: str = ''  # normalized string payload
    human: str = ''  # human-readable label

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
