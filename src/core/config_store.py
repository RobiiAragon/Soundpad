import json
import os
import tempfile
from typing import Any, Dict


def config_dir() -> str:
    appdata = os.getenv('APPDATA') or os.path.expanduser('~')
    return os.path.join(appdata, 'USB-Sound-Mapper')


def _defaults() -> Dict[str, Any]:
    return {
        'selected_device': {'type': 'keyboard'},
        'mappings': [],
    }


class ConfigStore:
    def __init__(self, directory: str = ''):
        self.dir = directory or config_dir()
        self.path = os.path.join(self.dir, 'config.json')
        self.data: Dict[str, Any] = _defaults()
        self.load()

    def load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
        except (OSError, ValueError):
            return
        # Ignore a config that is not the expected shape instead of crashing later.
        if not isinstance(loaded, dict):
            return
        data = _defaults()
        if isinstance(loaded.get('selected_device'), dict):
            data['selected_device'] = loaded['selected_device']
        if isinstance(loaded.get('mappings'), list):
            data['mappings'] = [m for m in loaded['mappings'] if isinstance(m, dict)]
        for k, v in loaded.items():
            data.setdefault(k, v)
        self.data = data

    def save(self) -> bool:
        """Write atomically so a crash mid-save never leaves a corrupt config.json."""
        try:
            os.makedirs(self.dir, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.dir, prefix='config.', suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                raise
            return True
        except OSError:
            return False
