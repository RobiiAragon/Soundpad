from dataclasses import dataclass
from typing import List, Optional

try:
    import pywinusb.hid as hid
except Exception:  # pragma: no cover
    hid = None


@dataclass
class HidDeviceInfo:
    vendor_id: int
    product_id: int
    vendor_name: Optional[str]
    product_name: Optional[str]


def list_hid_devices() -> List[HidDeviceInfo]:
    devices: List[HidDeviceInfo] = []
    if not hid:
        return devices
    seen = set()
    for d in hid.HidDeviceFilter().get_devices():
        try:
            key = (d.vendor_id, d.product_id)
            if key in seen:
                continue
            seen.add(key)
            devices.append(HidDeviceInfo(
                vendor_id=d.vendor_id,
                product_id=d.product_id,
                vendor_name=d.vendor_name,
                product_name=d.product_name,
            ))
        except Exception:
            continue
    return devices
