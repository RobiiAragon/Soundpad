import threading
from typing import Callable, Dict, Optional, Tuple

from .types import EventSignature


try:
    from pynput import keyboard, mouse
except Exception:  # pragma: no cover
    keyboard = None
    mouse = None

try:
    import pywinusb.hid as hid
except Exception:  # pragma: no cover
    hid = None


Callback = Callable[[], None]


class DeviceListener:
    def __init__(self, dtype: str, dinfo: Dict):
        self.dtype = dtype  # 'hid' | 'keyboard' | 'mouse'
        self.dinfo = dinfo
        self.is_running = False
        self._bindings: Dict[str, Callback] = {}
        self._capture_callback: Optional[Callable[[EventSignature], None]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._hid_device = None
        self._kb_listener = None
        self._mouse_listener = None

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
        self.is_running = False

    def capture_next(self, callback: Callable[[EventSignature], None]):
        # Start a short-lived listener to capture 1st event
        self._capture_callback = callback

    def _emit_capture(self, sig: EventSignature):
        cb = self._capture_callback
        self._capture_callback = None
        if cb:
            cb(sig)

    def _sig_key(self, sig: EventSignature) -> str:
        return f"{sig.type}:{sig.vendor_id}:{sig.product_id}:{sig.code}"

    def _run(self):
        if self.dtype == 'keyboard':
            self._run_keyboard()
        elif self.dtype == 'mouse':
            self._run_mouse()
        elif self.dtype == 'hid':
            self._run_hid()

    def _run_keyboard(self):
        if not keyboard:
            return

        def on_press(key):
            try:
                name = key.char if hasattr(key, 'char') and key.char else str(key)
            except Exception:
                name = str(key)
            sig = EventSignature(type='keyboard', code=name, human=f"Tecla {name}")
            if self._capture_callback:
                self._emit_capture(sig)
                return False  # stop capture
            cb = self._bindings.get(self._sig_key(sig))
            if cb:
                cb()

        self._kb_listener = keyboard.Listener(on_press=on_press)
        self._kb_listener.start()
        self._kb_listener.join()

    def _run_mouse(self):
        if not mouse:
            return

        def on_click(x, y, button, pressed):
            if not pressed:
                return
            name = str(button)
            sig = EventSignature(type='mouse', code=name, human=f"Mouse {name}")
            if self._capture_callback:
                self._emit_capture(sig)
                return False
            cb = self._bindings.get(self._sig_key(sig))
            if cb:
                cb()

        self._mouse_listener = mouse.Listener(on_click=on_click)
        self._mouse_listener.start()
        self._mouse_listener.join()

    def _run_hid(self):
        if not hid:
            return
        vid = self.dinfo.get('vendor_id')
        pid = self.dinfo.get('product_id')
        dev = None
        for d in hid.HidDeviceFilter(vendor_id=vid, product_id=pid).get_devices():
            dev = d
            break
        if not dev:
            return

        self._hid_device = dev
        self._hid_device.open()

        def raw_handler(data):
            # data is a list[int], first byte is report id
            if not data:
                return
            report_id = data[0]
            payload = bytes(data[1:])
            hex_code = f"{report_id:02X}-" + payload.hex().upper()
            sig = EventSignature(type='hid', vendor_id=vid, product_id=pid, code=hex_code, human=f"HID {vid:04X}:{pid:04X} [{hex_code}]")
            if self._capture_callback:
                self._emit_capture(sig)
                return
            cb = self._bindings.get(self._sig_key(sig))
            if cb:
                cb()

        self._hid_device.set_raw_data_handler(raw_handler)
        # Block until stop
        while not self._stop_event.is_set():
            self._stop_event.wait(0.2)
        try:
            self._hid_device.set_raw_data_handler(None)
        except Exception:
            pass
