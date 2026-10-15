"""BLE advertisement scanner built on *bleak* (BlueZ on Linux, WinRT on Windows, CoreBluetooth on macOS)."""

from __future__ import annotations

import logging
from typing import Callable

from ..protocol import proximity
from ..protocol.models import APPLE_VENDOR_ID

log = logging.getLogger(__name__)

AdvertCallback = Callable[[str, int | None, proximity.ProximityAdvert], None]


class BleScanner:
    def __init__(self, callback: AdvertCallback):
        self._callback = callback
        self._scanner = None
        self.running = False
        self.packets = 0

    async def start(self) -> None:
        if self.running:
            return
        from bleak import BleakScanner  # imported lazily: the CLI must work without a radio

        kwargs = {}
        try:
            import sys

            if sys.platform.startswith("linux"):
                # Ask BlueZ to forward every packet, not only the first per device.
                kwargs["bluez"] = {"filters": {"DuplicateData": True, "Transport": "le"}}
        except Exception:  # pragma: no cover - defensive
            pass
        self._scanner = BleakScanner(detection_callback=self._on_detect, **kwargs)
        await self._scanner.start()
        self.running = True
        log.info("BLE scanner started")

    async def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        try:
            await self._scanner.stop()
        except Exception as exc:  # noqa: BLE001
            log.debug("scanner stop: %s", exc)
        self._scanner = None
        log.info("BLE scanner stopped")

    def _on_detect(self, device, advertisement) -> None:
        data = advertisement.manufacturer_data.get(APPLE_VENDOR_ID)
        if not data:
            return
        adv = proximity.parse(bytes(data))
        if adv is None:
            return
        self.packets += 1
        try:
            self._callback(device.address, advertisement.rssi, adv)
        except Exception:  # noqa: BLE001
            log.exception("advert callback failed")
