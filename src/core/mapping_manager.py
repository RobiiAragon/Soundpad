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
        raw_id = d.get('id')
        return MappingItem(id=raw_id if isinstance(raw_id, int) else 0, signature=sig, audio=d.get('audio') or '')

class MappingManager:
    def __init__(self):
        self._items: List[MappingItem] = []
        self._next_id = 1

    def load(self, lst: List[Dict[str, Any]]):
        self._items.clear()
        self._next_id = 1
        items = []
        for raw in lst:
            try:
                items.append(MappingItem.from_dict(raw))
            except (KeyError, TypeError, AttributeError):
                continue  # skip malformed entries instead of refusing to start
        # Older configs saved mappings without an id (every row became id 0), which made
        # "remove" delete all of them at once. Give missing/duplicate ids a fresh one.
        self._next_id = max([i.id for i in items if i.id > 0], default=0) + 1
        seen = set()
        for item in items:
            if item.id <= 0 or item.id in seen:
                item.id = self._next_id
                self._next_id += 1
            seen.add(item.id)
            self._items.append(item)

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
