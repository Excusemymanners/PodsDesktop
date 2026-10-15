"""Fallback backend for platforms without classic-Bluetooth support: BLE scanning only."""

from __future__ import annotations

from .bluetooth import ConnectionCallback, PairedDevice


class NullBackend:
    async def start(self, on_connection_change: ConnectionCallback) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def paired_devices(self) -> list[PairedDevice]:
        return []

    async def is_connected(self, address: str) -> bool:
        return False

    async def connect(self, address: str) -> None:
        raise RuntimeError("connecting is not supported on this platform")

    async def disconnect(self, address: str) -> None:
        raise RuntimeError("disconnecting is not supported on this platform")

    async def adapter_powered(self) -> bool:
        return True

    async def power_on(self) -> None:
        raise RuntimeError("turning Bluetooth on is not supported on this platform")
