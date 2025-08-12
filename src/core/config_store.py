import json
import os
from typing import Any, Dict


class ConfigStore:
    def __init__(self):
        appdata = os.getenv('APPDATA') or os.path.expanduser('~')
        self.dir = os.path.join(appdata, 'USB-Sound-Mapper')
        self.path = os.path.join(self.dir, 'config.json')
        self.data: Dict[str, Any] = {
            'selected_device': {'type': 'keyboard'},
            'mappings': [],
        }
        self.load()

    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
        except Exception:
            pass

    def save(self):
        try:
            os.makedirs(self.dir, exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
