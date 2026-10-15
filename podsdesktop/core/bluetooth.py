"""Classic-Bluetooth side: which Apple devices are paired, are they connected, connect them.

Linux talks to BlueZ over D-Bus (dbus-fast, already pulled in by bleak); Windows uses WinRT.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from ..protocol.models import APPLE_VENDOR_ID, is_apple_audio_pid, lookup

log = logging.getLogger(__name__)

ConnectionCallback = Callable[[str, bool], Awaitable[None] | None]


@dataclass
class PairedDevice:
    address: str
    name: str
    vendor_id: int | None
    product_id: int | None
    connected: bool

    @property
    def is_apple_audio(self) -> bool:
        return self.vendor_id == APPLE_VENDOR_ID and self.product_id is not None and is_apple_audio_pid(self.product_id)

    @property
    def model_name(self) -> str:
        return lookup(self.product_id).name if self.product_id is not None else ""


class BluetoothBackend(Protocol):
    async def start(self, on_connection_change: ConnectionCallback) -> None: ...
    async def stop(self) -> None: ...
    async def paired_devices(self) -> list[PairedDevice]: ...
    async def is_connected(self, address: str) -> bool: ...
    async def connect(self, address: str) -> None: ...
    async def disconnect(self, address: str) -> None: ...
    async def adapter_powered(self) -> bool: ...


def create_backend() -> BluetoothBackend:
    if sys.platform.startswith("linux"):
        from .bluetooth_linux import BlueZBackend

        return BlueZBackend()
    if sys.platform == "win32":
        from .bluetooth_windows import WinRTBackend

        return WinRTBackend()
    from .bluetooth_null import NullBackend

    return NullBackend()
