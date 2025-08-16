from __future__ import annotations
import threading, time
from typing import Callable, List

_lock = threading.Lock()
_callbacks: List[Callable[[str], None]] = []
_buffer: List[str] = []
_max_lines = 5000  # simple cap

def register(cb: Callable[[str], None]):
    with _lock:
        _callbacks.append(cb)
        # Flush existing buffer to new consumer
        for line in _buffer:
            try:
                cb(line)
            except Exception:
                pass

def unregister(cb: Callable[[str], None]):
    with _lock:
        if cb in _callbacks:
            _callbacks.remove(cb)

def has_listeners() -> bool:
    with _lock:
        return bool(_callbacks)

def log(msg: str):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    with _lock:
        _buffer.append(line)
        if len(_buffer) > _max_lines:
            # Drop oldest lines
            excess = len(_buffer) - _max_lines
            if excess > 0:
                del _buffer[:excess]
        callbacks = list(_callbacks)
    for cb in callbacks:
        try:
            cb(line)
        except Exception:
            pass

__all__ = ['log','register','unregister','has_listeners']
