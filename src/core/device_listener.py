"""Device listeners with multi-device capture and runtime combo aggregation."""

from __future__ import annotations

import os, time, threading
from typing import Callable, Dict, Optional
from .types import EventSignature

try:
    from . import logger as _central_logger  # type: ignore
except Exception:  # pragma: no cover
    _central_logger = None

try:
    from pynput import keyboard, mouse  # type: ignore
except Exception:  # pragma: no cover
    keyboard = None  # type: ignore
    mouse = None  # type: ignore

try:
    import pywinusb.hid as hid  # type: ignore
except Exception:  # pragma: no cover
    hid = None  # type: ignore

Callback = Callable[[], None]


class DeviceListener:
    def __init__(self, dtype: str, dinfo: Dict):
        self.dtype = dtype
        self.dinfo = dinfo
        self.is_running = False
        self._bindings: Dict[str, Callback] = {}
        self._capture_callback = None
        self._capture_keep_open = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # Resources
        self._hid_device = None
        self._kb_listener = None
        self._mouse_listener = None
        # Keyboard state
        self._pressed_keys = set()
        self._fired_combos = set()
        # Capture state
        self._capture_keys = set()
        self._capture_timer = None
        # Parent multi listener (set when part of MultiDeviceListener)
        self._parent_multidevice = None  # type: ignore

    def bind(self, sig: EventSignature, cb: Callback):
        self._bindings[self._sig_key(sig)] = cb

    def start(self):
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.is_running = True

    def stop(self):
        self._stop_event.set()
        for attr in ['_kb_listener', '_mouse_listener']:
            lst = getattr(self, attr, None)
            if lst:
                try:
                    lst.stop()
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._hid_device:
            try:
                self._hid_device.close()
            except Exception:
                pass
            self._hid_device = None
        if self._capture_timer:
            try:
                self._capture_timer.cancel()
            except Exception:
                pass
            self._capture_timer = None
        self.is_running = False

    def capture_next(self, callback: Callable[[EventSignature], None], keep_open: bool = False):
        self._capture_callback = callback
        self._capture_keep_open = keep_open

    def _emit_capture(self, sig: EventSignature):
        cb = self._capture_callback
        if not self._capture_keep_open:
            self._capture_callback = None
        if cb:
            cb(sig)

    def _sig_key(self, sig: EventSignature) -> str:
        return f"{sig.type}:{sig.vendor_id}:{sig.product_id}:{sig.code}"

    def _run(self):
        try:
            if self.dtype == 'keyboard':
                self._run_keyboard()
            elif self.dtype == 'mouse':
                self._run_mouse()
            elif self.dtype == 'hid':
                self._run_hid()
        except Exception as e:  # pragma: no cover
            if _central_logger and _central_logger.has_listeners():
                _central_logger.log(f"[listener] error {self.dtype}: {e}")

    # ---- keyboard ----
    def _run_keyboard(self):  # noqa: C901
        if not keyboard:
            return

        def norm(k):
            try:
                if getattr(k, 'char', None):
                    return k.char.lower()
            except Exception:
                pass
            s = str(k)
            if s.startswith('Key.'):
                s = s[4:]
            repl = {'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl', 'alt_l': 'alt', 'alt_r': 'alt', 'shift_l': 'shift', 'shift_r': 'shift', 'cmd': 'meta', 'cmd_l': 'meta', 'cmd_r': 'meta', 'windows': 'meta', 'esc': 'escape'}
            return repl.get(s, s).lower()

        def human(keys):
            pretty = {'ctrl': 'Ctrl', 'alt': 'Alt', 'shift': 'Shift', 'meta': 'Win'}
            parts = [pretty.get(k, k.upper() if len(k) == 1 else k.capitalize()) for k in keys]
            return ("Tecla " if len(keys) == 1 else "Combo ") + '+'.join(parts)

        def code(keys):
            return '+'.join(keys)

        def fire(combo):
            sig = EventSignature(type='keyboard', code=combo, human=human(combo.split('+')))
            cb = self._bindings.get(self._sig_key(sig))
            if not cb and '+' not in combo:
                legacy = EventSignature(type='keyboard', code=f"Key.{combo}", human=sig.human)
                cb = self._bindings.get(self._sig_key(legacy))
            if cb:
                cb()
                if _central_logger and _central_logger.has_listeners():
                    _central_logger.log(f"[keyboard] trigger {combo}")
            # Always notify parent for multi aggregation
            parent = getattr(self, '_parent_multidevice', None)
            if parent:
                try:
                    parent._on_raw_event(sig)  # type: ignore
                except Exception:
                    pass

        def finalize():
            self._capture_timer = None
            if not self._capture_callback:
                return
            keys = sorted(self._capture_keys)
            if not keys:
                return
            sig = EventSignature(type='keyboard', code=code(keys), human=human(keys))
            try:
                if _central_logger:
                    print(f"[capture] keyboard: {sig.code}")
            except Exception:
                pass
            self._capture_keys.clear()
            self._emit_capture(sig)
            if not self._capture_keep_open and self._kb_listener:
                try:
                    self._kb_listener.stop()
                except Exception:
                    pass

        def schedule():
            if self._capture_timer:
                try:
                    self._capture_timer.cancel()
                except Exception:
                    pass
            self._capture_timer = threading.Timer(0.7, finalize)
            self._capture_timer.daemon = True
            self._capture_timer.start()

        def on_press(k):
            name = norm(k)
            if self._capture_callback:
                self._capture_keys.add(name)
                schedule()
                return
            self._pressed_keys.add(name)
            keys_sorted = sorted(self._pressed_keys)
            combo = code(keys_sorted)
            if combo not in self._fired_combos:
                fire(combo)
                self._fired_combos.add(combo)
            if len(keys_sorted) > 1 and name not in ['shift', 'ctrl', 'alt', 'meta']:
                if name not in self._fired_combos:
                    fire(name)
                    self._fired_combos.add(name)

        def on_release(k):
            name = norm(k)
            if name in self._pressed_keys:
                self._pressed_keys.remove(name)
            for c in [c for c in self._fired_combos if name in c.split('+')]:
                self._fired_combos.remove(c)
            if self._capture_callback and not self._capture_keys:
                finalize()

        self._kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._kb_listener.start()
        self._kb_listener.join()

    # ---- mouse ----
    def _run_mouse(self):  # noqa: C901
        if not mouse:
            return
        pressed, fired = set(), set()
        cap, cap_timer = set(), {'t': None}

        def norm(btn):
            s = str(btn)
            return s[7:] if s.startswith('Button.') else s

        def human(btns):
            pretty = {'left': 'Izq', 'right': 'Der', 'middle': 'Centro'}
            parts = [pretty.get(b, b.capitalize()) for b in btns]
            return ("Mouse " if len(btns) == 1 else "Combo Mouse ") + '+'.join(parts)

        def code(btns):
            return '+'.join(btns)

        def fire(combo):
            sig = EventSignature(type='mouse', code=combo, human=human(combo.split('+')))
            cb = self._bindings.get(self._sig_key(sig))
            if cb:
                cb()
            parent = getattr(self, '_parent_multidevice', None)
            if parent:
                try:
                    parent._on_raw_event(sig)  # type: ignore
                except Exception:
                    pass

        def finalize():
            cap_timer['t'] = None
            if not self._capture_callback:
                return
            btns = sorted(cap)
            if not btns:
                return
            sig = EventSignature(type='mouse', code=code(btns), human=human(btns))
            cap.clear()
            self._emit_capture(sig)
            if not self._capture_keep_open and self._mouse_listener:
                try:
                    self._mouse_listener.stop()
                except Exception:
                    pass

        def schedule():
            if cap_timer['t']:
                try:
                    cap_timer['t'].cancel()
                except Exception:
                    pass
            t = threading.Timer(0.7, finalize)
            t.daemon = True
            t.start()
            cap_timer['t'] = t

        def on_click(_x, _y, button, pressed_flag):
            name = norm(button)
            if self._capture_callback:
                if pressed_flag:
                    cap.add(name)
                    schedule()
                else:
                    if not cap:
                        finalize()
                return
            if pressed_flag:
                pressed.add(name)
                btns_sorted = sorted(pressed)
                combo = code(btns_sorted)
                if combo not in fired:
                    fire(combo)
                    fired.add(combo)
                if len(btns_sorted) > 1 and name not in fired:
                    fire(name)
                    fired.add(name)
            else:
                if name in pressed:
                    pressed.remove(name)
                for c in [c for c in fired if name in c.split('+')]:
                    fired.remove(c)

        self._mouse_listener = mouse.Listener(on_click=on_click)
        self._mouse_listener.start()
        self._mouse_listener.join()

    # ---- hid ----
    def _run_hid(self):  # noqa: C901
        if not hid:
            return
        vid = self.dinfo.get('vendor_id')
        pid = self.dinfo.get('product_id')
        debug = os.getenv('SP_DEBUG_HID') == '1'
        dev = None
        candidates = list(hid.HidDeviceFilter(vendor_id=vid, product_id=pid).get_devices())
        preferred = []
        for d in candidates:
            try:
                for col in getattr(d, 'top_level_collections', []) or []:
                    if getattr(col, 'usage_page', None) == 0x01 and getattr(col, 'usage', None) == 0x06:
                        preferred.append(d)
                        break
            except Exception:
                pass
        for d in preferred + [c for c in candidates if c not in preferred]:
            dev = d
            break
        if not dev:
            return
        self._hid_device = dev
        self._hid_device.open()
        pressed, fired = set(), set()
        last = {'t': 0.0}

        def cleanup():
            if time.time() - last['t'] > 0.6:
                pressed.clear(); fired.clear()

        def human(codes):
            if len(codes) == 1:
                return f"HID {vid:04X}:{pid:04X} [{next(iter(codes))}]"
            return f"HID Combo {vid:04X}:{pid:04X} [{'+'.join(sorted(codes))}]"

        def raw(data):
            if not data:
                return
            report = data[0]; payload = bytes(data[1:])
            code = f"{report:02X}-" + payload.hex().upper()
            last['t'] = time.time(); cleanup()
            if debug:
                try: print(f"[hid] {code}")
                except Exception: pass
            if self._capture_callback:
                pressed.add(code)
                sig = EventSignature(type='hid', vendor_id=vid, product_id=pid, code='+'.join(sorted(pressed)), human=human(pressed))
                self._emit_capture(sig)
                if not self._capture_keep_open:
                    return
            pressed.add(code)
            combo = '+'.join(sorted(pressed)); h = human(pressed)
            if combo not in fired:
                sig = EventSignature(type='hid', vendor_id=vid, product_id=pid, code=combo, human=h)
                cb = self._bindings.get(self._sig_key(sig))
                if cb: cb()
                fired.add(combo)
                parent = getattr(self, '_parent_multidevice', None)
                if parent:
                    try:
                        parent._on_raw_event(sig)  # type: ignore
                    except Exception:
                        pass
            if code not in fired:
                single = EventSignature(type='hid', vendor_id=vid, product_id=pid, code=code, human=human({code}))
                cb = self._bindings.get(self._sig_key(single))
                if cb: cb()
                fired.add(code)
                parent = getattr(self, '_parent_multidevice', None)
                if parent:
                    try:
                        parent._on_raw_event(single)  # type: ignore
                    except Exception:
                        pass

        self._hid_device.set_raw_data_handler(raw)
        while not self._stop_event.is_set():
            self._stop_event.wait(0.2)
        try:
            self._hid_device.set_raw_data_handler(None)
        except Exception:
            pass


class MultiDeviceListener:
    """Aggregates keyboard/mouse/HID for capture and runtime multi-combos."""

    def __init__(self):
        self.is_running = False
        self._listeners = [DeviceListener('keyboard', {}), DeviceListener('mouse', {})]
        try:
            from .hid_devices import list_hid_devices  # type: ignore
            for dev in list_hid_devices():
                self._listeners.append(DeviceListener('hid', {'vendor_id': dev.vendor_id, 'product_id': dev.product_id}))
        except Exception:
            pass
        self._capture_lock = threading.Lock()
        self._capture_done = False
        self._multi_bindings: Dict[str, Callback] = {}
        # runtime aggregation state
        self._md_tokens = set()
        self._md_last_time = 0.0
        self._md_timeout = 0.6
        self._md_fired = set()
        self._md_lock = threading.Lock()

    def bind(self, sig: EventSignature, cb: Callback):
        if sig.type == 'multi':
            self._multi_bindings[f"multi::{sig.code}"] = cb
            return
        for l in self._listeners:
            l.bind(sig, cb)

    def start(self):
        if self.is_running:
            return
        for l in self._listeners:
            try:
                l._parent_multidevice = self  # type: ignore
                l.start()
            except Exception: pass
        self.is_running = True

    def stop(self):
        for l in self._listeners:
            try: l.stop()
            except Exception: pass
        self.is_running = False
        with self._capture_lock:
            self._capture_done = True

    def capture_next(self, callback: Callable[[EventSignature], None]):
        with self._capture_lock:
            self._capture_done = False
        agg = {'tokens': set(), 'types': set(), 'first': None, 'timer': None}
        lock = threading.Lock(); timeout = 0.7

        def schedule():
            if agg['timer']:
                try: agg['timer'].cancel()
                except Exception: pass
            t = threading.Timer(timeout, finalize); t.daemon = True; t.start(); agg['timer'] = t

        def finalize():
            with lock:
                if self._capture_done: return
                self._capture_done = True
            try:
                if len(agg['tokens']) >= 2 and len(agg['types']) >= 2:
                    code = '+'.join(sorted(agg['tokens']))
                    sig = EventSignature(type='multi', code=code, human=f"Multi {code}")
                else:
                    sig = agg['first'] if agg['first'] else EventSignature(type='keyboard', code='', human='')
                callback(sig)
            finally:
                self.stop()

        def on_sig(sig: EventSignature):
            with lock:
                if self._capture_done: return
                if not agg['first']: agg['first'] = sig
                if sig.type == 'keyboard': token = f"kb:{sig.code}"
                elif sig.type == 'mouse': token = f"ms:{sig.code}"
                elif sig.type == 'hid': token = f"hid:{sig.vendor_id}:{sig.product_id}:{sig.code}"
                else: token = f"{sig.type}:{sig.code}"
                agg['tokens'].add(token); agg['types'].add(sig.type); schedule()

        for l in self._listeners:
            try: l.capture_next(on_sig, keep_open=True)
            except Exception: pass

    # runtime multi-trigger after individual mappings fire
    def _on_raw_event(self, sig: EventSignature):
        now = time.time()
        with self._md_lock:
            if now - self._md_last_time > self._md_timeout:
                self._md_tokens.clear(); self._md_fired.clear()
            self._md_last_time = now
            if sig.type == 'keyboard': token = f"kb:{sig.code}"
            elif sig.type == 'mouse': token = f"ms:{sig.code}"
            elif sig.type == 'hid': token = f"hid:{sig.vendor_id}:{sig.product_id}:{sig.code}"
            else: return
            self._md_tokens.add(token)
            # Need at least two device types
            types = set()
            for t in self._md_tokens:
                if t.startswith('kb:'): types.add('kb')
                elif t.startswith('ms:'): types.add('ms')
                elif t.startswith('hid:'): types.add('hid')
            if len(types) < 2:
                return
            code = '+'.join(sorted(self._md_tokens))
            key = f"multi::{code}"
            if key in self._multi_bindings and key not in self._md_fired:
                try: self._multi_bindings[key]()
                except Exception: pass
                self._md_fired.add(key)
