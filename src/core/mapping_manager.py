from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from .types import EventSignature

@dataclass
class MappingItem:
    id: int
    signature: Optional[EventSignature] = None
    audio: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'signature': self.signature.to_dict() if self.signature else None,
            'audio': self.audio,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> 'MappingItem':
        sigdata = d.get('signature')
        sig = EventSignature.from_dict(sigdata) if sigdata else None
        return MappingItem(id=d.get('id', 0), signature=sig, audio=d.get('audio',''))

class MappingManager:
    def __init__(self):
        self._items: List[MappingItem] = []
        self._next_id = 1

    def load(self, lst: List[Dict[str, Any]]):
        self._items.clear()
        self._next_id = 1
        for raw in lst:
            item = MappingItem.from_dict(raw)
            self._items.append(item)
            self._next_id = max(self._next_id, item.id + 1)

    def serialize(self) -> List[Dict[str, Any]]:
        return [i.to_dict() for i in self._items]

    def add(self) -> MappingItem:
        item = MappingItem(id=self._next_id)
        self._next_id += 1
        self._items.append(item)
        return item

    def remove_ids(self, ids: List[int]):
        ids_set = set(ids)
        self._items = [i for i in self._items if i.id not in ids_set]

    def items(self) -> List[MappingItem]:
        return list(self._items)

    def get_by_row(self, row: int) -> Optional[MappingItem]:
        try:
            return self._items[row]
        except IndexError:
            return None

    def detect_duplicates(self) -> Dict[str, List[MappingItem]]:
        """Return mapping from signature code to items if more than one shares it."""
        buckets: Dict[str,List[MappingItem]] = {}
        for m in self._items:
            if m.signature:
                key = f"{m.signature.type}:{m.signature.vendor_id}:{m.signature.product_id}:{m.signature.code}"
                buckets.setdefault(key, []).append(m)
        return {k:v for k,v in buckets.items() if len(v) > 1}
