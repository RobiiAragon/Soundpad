import threading
import sys
from typing import Callable, Dict, Optional

from .types import EventSignature
try:
    from . import logger as _central_logger
except Exception:  # pragma: no cover
    _central_logger = None


try:
    from pynput import keyboard, mouse
except Exception:  # pragma: no cover
    keyboard = None
    mouse = None

try:
    import pywinusb.hid as hid
except Exception:  # pragma: no cover
    hid = None

# MIDI support removed


Callback = Callable[[], None]


class DeviceListener:
    def __init__(self, dtype: str, dinfo: Dict):
        # Device meta
        self.dtype = dtype  # 'hid' | 'keyboard' | 'mouse'
        self.dinfo = dinfo
        # State
        self.is_running = False
        self._bindings: Dict[str, Callback] = {}
        self._capture_callback = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # Underlying listeners/handles
        self._hid_device = None
        self._kb_listener = None
        self._mouse_listener = None
        # Keyboard combo state
        self._pressed_keys = set()
        self._fired_combos = set()
        # Capture helpers
        self._capture_keys = set()
        self._capture_timer = None

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
        if self._kb_listener:
            try:
                self._kb_listener.stop()
            except Exception:
                pass
            self._kb_listener = None
        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None
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

    def capture_next(self, callback: Callable[[EventSignature], None]):
        self._capture_callback = callback

    def _emit_capture(self, sig: EventSignature):
        cb = self._capture_callback
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
        except Exception as e:  # Robust guard
            if _central_logger and _central_logger.has_listeners():
                _central_logger.log(f"[listener] error {self.dtype}: {e}")
            import traceback
            traceback.print_exc()
    # MIDI removido

    def _run_keyboard(self):
        if not keyboard:
            return
        def norm_key(k) -> str:
            try:
                if hasattr(k, 'char') and k.char:
                    return k.char.lower()
            except Exception:
                pass
            s = str(k)
            if s.startswith('Key.'):
                s = s[4:]
            # Unify common modifier names
            replacements = {
                'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
                'alt_l': 'alt', 'alt_r': 'alt',
                'shift_l': 'shift', 'shift_r': 'shift',
                'cmd': 'meta', 'cmd_l': 'meta', 'cmd_r': 'meta',
                'windows': 'meta', 'esc': 'escape'
            }
            return replacements.get(s, s).lower()

        def humanize_combo(keys: list[str]) -> str:
            label_parts = []
            pretty = {
                'ctrl': 'Ctrl', 'alt': 'Alt', 'shift': 'Shift', 'meta': 'Win'
            }
            for k in keys:
                label_parts.append(pretty.get(k, k.upper() if len(k) == 1 else k.capitalize()))
            if len(keys) == 1:
                return f"Tecla {'+'.join(label_parts)}"
            return f"Combo {'+'.join(label_parts)}"

        def combo_code(keys: list[str]) -> str:
            return '+'.join(keys)

        def fire_if_bound(code: str, human: str):
            sig = EventSignature(type='keyboard', code=code, human=human)
            cb = self._bindings.get(self._sig_key(sig))
            # Legacy single-key code style (e.g., 'Key.space') support
            if not cb and '+' not in code:
                legacy_sig = EventSignature(type='keyboard', code=f"Key.{code}", human=human)
                cb = self._bindings.get(self._sig_key(legacy_sig))
            if cb:
                cb()
                if _central_logger and _central_logger.has_listeners():
                    _central_logger.log(f"[keyboard] trigger code={code} human={human}")

        def finalize_capture():
            self._capture_timer = None
            if not self._capture_callback:
                return
            keys = sorted(self._capture_keys)
            if not keys:
                # Nothing captured
                return
            code = combo_code(keys)
            human = humanize_combo(keys)
            sig = EventSignature(type='keyboard', code=code, human=human)
            try:
                msg = f"[capture] keyboard: {code}"
                print(msg, file=sys.stdout, flush=True)
                if _central_logger:
                    _central_logger.log(msg)
            except Exception:
                pass
            self._capture_keys.clear()
            self._emit_capture(sig)
            # Stop listener after capture
            try:
                if self._kb_listener:
                    self._kb_listener.stop()
            except Exception:
                pass

        def schedule_finalize_capture():
            if self._capture_timer:
                try:
                    self._capture_timer.cancel()
                except Exception:
                    pass
            self._capture_timer = threading.Timer(0.7, finalize_capture)
            self._capture_timer.daemon = True
            self._capture_timer.start()

        def on_press(k):
            try:
                name = norm_key(k)
                if _central_logger and _central_logger.has_listeners():
                    _central_logger.log(f"[keyboard] press {name}")
                if self._capture_callback:
                    self._capture_keys.add(name)
                    schedule_finalize_capture()
                    return
                self._pressed_keys.add(name)
                keys_sorted = sorted(self._pressed_keys)
                code = combo_code(keys_sorted)
                if code not in self._fired_combos:
                    human = humanize_combo(keys_sorted)
                    fire_if_bound(code, human)
                    self._fired_combos.add(code)
                if len(keys_sorted) > 1 and name not in ['shift', 'ctrl', 'alt', 'meta']:
                    single_code = name
                    if single_code not in self._fired_combos:
                        human = humanize_combo([name])
                        fire_if_bound(single_code, human)
                        self._fired_combos.add(single_code)
            except Exception as e:
                if _central_logger and _central_logger.has_listeners():
                    _central_logger.log(f"[keyboard] error on_press: {e}")

        def on_release(k):
            try:
                name = norm_key(k)
                if _central_logger and _central_logger.has_listeners():
                    _central_logger.log(f"[keyboard] release {name}")
                if name in self._pressed_keys:
                    self._pressed_keys.remove(name)
                to_remove = [c for c in self._fired_combos if name in c.split('+')]
                for c in to_remove:
                    self._fired_combos.remove(c)
                if self._capture_callback and not self._capture_keys:
                    finalize_capture()
            except Exception as e:
                if _central_logger and _central_logger.has_listeners():
                    _central_logger.log(f"[keyboard] error on_release: {e}")

        self._kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._kb_listener.start()
        self._kb_listener.join()

    def _run_mouse(self):
        if not mouse:
            return
        # Local state so it doesn't clash with keyboard combo tracking
        pressed_buttons = set()  # raw button names
        fired_combos = set()
        capture_buttons = set()
        capture_timer = {
            'timer': None
        }

        def norm_btn(btn) -> str:
            s = str(btn)
            # pynput mouse buttons look like Button.left
            if s.startswith('Button.'):
                return s[7:]
            return s

        def humanize(btns: list[str]) -> str:
            pretty = {
                'left': 'Izq', 'right': 'Der', 'middle': 'Centro'
            }
            parts = [pretty.get(b, b.capitalize()) for b in btns]
            if len(btns) == 1:
                return f"Mouse {'+'.join(parts)}"
            return f"Combo Mouse {'+'.join(parts)}"

        def combo_code(btns: list[str]) -> str:
            return '+'.join(btns)

        def fire_if_bound(code: str, human: str):
            sig = EventSignature(type='mouse', code=code, human=human)
            cb = self._bindings.get(self._sig_key(sig))
            if cb:
                cb()
                if _central_logger and _central_logger.has_listeners():
                    _central_logger.log(f"[mouse] trigger code={code} human={human}")

        def finalize_capture():
            capture_timer['timer'] = None
            if not self._capture_callback:
                return
            btns = sorted(capture_buttons)
            if not btns:
                return
            code = combo_code(btns)
            sig = EventSignature(type='mouse', code=code, human=humanize(btns))
            try:
                msg = f"[capture] mouse: {code}"
                print(msg, file=sys.stdout, flush=True)
                if _central_logger:
                    _central_logger.log(msg)
            except Exception:
                pass
            capture_buttons.clear()
            self._emit_capture(sig)
            try:
                if self._mouse_listener:
                    self._mouse_listener.stop()
            except Exception:
                pass

        def schedule_finalize_capture():
            t = capture_timer['timer']
            if t:
                try:
                    t.cancel()
                except Exception:
                    pass
            new_t = threading.Timer(0.7, finalize_capture)
            new_t.daemon = True
            new_t.start()
            capture_timer['timer'] = new_t

        def on_click(x, y, button, pressed):
            name = norm_btn(button)
            if _central_logger and _central_logger.has_listeners():
                _central_logger.log(f"[mouse] {'down' if pressed else 'up'} {name} @ {x},{y}")
            if self._capture_callback:
                if pressed:
                    capture_buttons.add(name)
                    schedule_finalize_capture()
                else:
                    # If released and no more buttons, finalize early
                    if not capture_buttons:
                        finalize_capture()
                return
            # Normal listening
            if pressed:
                pressed_buttons.add(name)
                btns_sorted = sorted(pressed_buttons)
                code = combo_code(btns_sorted)
                if code not in fired_combos:
                    fire_if_bound(code, humanize(btns_sorted))
                    fired_combos.add(code)
                # También dispara el botón individual recién presionado si hay binding
                if len(btns_sorted) > 1:
                    single_code = name
                    if single_code not in fired_combos:
                        fire_if_bound(single_code, humanize([name]))
                        fired_combos.add(single_code)
            else:
                if name in pressed_buttons:
                    pressed_buttons.remove(name)
                # Clear fired combos containing released button
                to_remove = [c for c in fired_combos if name in c.split('+')]
                for c in to_remove:
                    fired_combos.remove(c)

        self._mouse_listener = mouse.Listener(on_click=on_click)
        self._mouse_listener.start()
        self._mouse_listener.join()

    def _run_hid(self):
        if not hid:
            return
        vid = self.dinfo.get('vendor_id')
        pid = self.dinfo.get('product_id')
        import os
        debug_hid = os.getenv('SP_DEBUG_HID') == '1'
        dev = None
        candidates = list(hid.HidDeviceFilter(vendor_id=vid, product_id=pid).get_devices())
        # Prefer keyboard interface (usage_page 0x01, usage 0x06) if available
        preferred = []
        for d in candidates:
            try:
                for col in getattr(d, 'top_level_collections', []) or []:
                    if getattr(col, 'usage_page', None) == 0x01 and getattr(col, 'usage', None) == 0x06:
                        preferred.append(d)
                        break
            except Exception:
                pass
        search_order = preferred + [c for c in candidates if c not in preferred]
        for d in search_order:
            dev = d
            if debug_hid:
                try:
                    print(f"[hid] Seleccionado dispositivo path={getattr(d,'device_path',None)} preferido={d in preferred}", flush=True)
                except Exception:
                    pass
            break
        if not dev:
            return

        self._hid_device = dev
        self._hid_device.open()

        # Combo tracking for HID: we treat each unique hex_code as a button; maintain a set for ~short window
        pressed_codes = set()
        fired_combos = set()
        last_update = {'time': 0.0}

        def cleanup_expired():
            # Simple timeout to reset combos if no activity (0.6s)
            import time
            if time.time() - last_update['time'] > 0.6:
                pressed_codes.clear()
                fired_combos.clear()

        def make_human(codes):
            if len(codes) == 1:
                return f"HID {vid:04X}:{pid:04X} [{next(iter(codes))}]"
            return f"HID Combo {vid:04X}:{pid:04X} [{'+'.join(sorted(codes))}]"

        def raw_handler(data):
            if not data:
                return
            import time
            report_id = data[0]
            payload = bytes(data[1:])
            hex_code = f"{report_id:02X}-" + payload.hex().upper()
            if _central_logger and _central_logger.has_listeners():
                _central_logger.log(f"[hid] report id={report_id:02X} payload={payload.hex()}")
            last_update['time'] = time.time()
            cleanup_expired()
            if debug_hid:
                try:
                    print(f"[hid] report id={report_id:02X} len={len(payload)} code={hex_code}", flush=True)
                except Exception:
                    pass
            # For capture, aggregate until idle window similar to keyboard (reuse timer approach simplified)
            if self._capture_callback:
                pressed_codes.add(hex_code)
                # Directly finalize after short inactivity simulated by timer on main thread not available: capture immediate single or multi (second press merges)
                sig = EventSignature(type='hid', vendor_id=vid, product_id=pid,
                                     code='+'.join(sorted(pressed_codes)),
                                     human=make_human(pressed_codes))
                try:
                    msg = f"[capture] hid: {sig.code}"
                    print(msg, file=sys.stdout, flush=True)
                    if _central_logger:
                        _central_logger.log(msg)
                except Exception:
                    pass
                self._emit_capture(sig)
                return
            # Normal listening: build combo code
            pressed_codes.add(hex_code)
            codes_sorted = sorted(pressed_codes)
            combo_code = '+'.join(codes_sorted)
            human = make_human(pressed_codes)
            if combo_code not in fired_combos:
                sig = EventSignature(type='hid', vendor_id=vid, product_id=pid, code=combo_code, human=human)
                cb = self._bindings.get(self._sig_key(sig))
                if cb:
                    cb()
                fired_combos.add(combo_code)
            # Dispara también el código individual recién presionado si existe binding
            if hex_code not in fired_combos:
                single_sig = EventSignature(type='hid', vendor_id=vid, product_id=pid, code=hex_code, human=make_human({hex_code}))
                cb_single = self._bindings.get(self._sig_key(single_sig))
                if cb_single:
                    cb_single()
                fired_combos.add(hex_code)

        self._hid_device.set_raw_data_handler(raw_handler)
        # Block until stop
        while not self._stop_event.is_set():
            self._stop_event.wait(0.2)
        try:
            self._hid_device.set_raw_data_handler(None)
        except Exception:
            pass

    # _run_midi removed


class MultiDeviceListener:
    """Composite listener that runs keyboard, mouse, and all HID devices at once."""
    def __init__(self):
        self.is_running = False
        self._listeners: list[DeviceListener] = []
        self._capture_lock = threading.Lock()
        self._capture_done = False

        # Always include global keyboard and mouse
        self._listeners.append(DeviceListener('keyboard', {}))
        self._listeners.append(DeviceListener('mouse', {}))
    # MIDI listeners removidos

        # Include all HID devices available at construction time
        try:
            from .hid_devices import list_hid_devices
            for dev in list_hid_devices():
                self._listeners.append(DeviceListener('hid', {
                    'vendor_id': dev.vendor_id,
                    'product_id': dev.product_id,
                }))
        except Exception:
            # If HID not available, proceed with keyboard/mouse only
            pass

    def bind(self, sig: EventSignature, cb: Callback):
        # Bind into all underlying listeners; the signature specificity ensures only matches will fire
        for l in self._listeners:
            l.bind(sig, cb)

    def start(self):
        if self.is_running:
            return
        for l in self._listeners:
            try:
                l.start()
            except Exception:
                # carry on even if one device fails
                pass
        self.is_running = True

    def stop(self):
        for l in self._listeners:
            try:
                l.stop()
            except Exception:
                pass
        self.is_running = False
        with self._capture_lock:
            self._capture_done = True

    def capture_next(self, callback: Callable[[EventSignature], None]):
        # Arm capture on all listeners and ensure only the first event wins.
        with self._capture_lock:
            self._capture_done = False

        def once(sig: EventSignature):
            with self._capture_lock:
                if self._capture_done:
                    return
                self._capture_done = True
            try:
                callback(sig)
            finally:
                # stop all after capture
                self.stop()

        for l in self._listeners:
            try:
                l.capture_next(once)
            except Exception:
                pass
