"""Windows backend through WinRT (the ``winrt-Windows.Devices.Bluetooth`` family of packages,
which bleak installs). Enumerates paired devices with their vendor/product ids and watches the
connection status. Connecting on demand has no public WinRT API, so it is not offered here.
"""

from __future__ import annotations

import asyncio
import logging

from .bluetooth import ConnectionCallback, PairedDevice

log = logging.getLogger(__name__)

PROP_VID = "System.DeviceInterface.Bluetooth.VendorId"
PROP_PID = "System.DeviceInterface.Bluetooth.ProductId"


def _format_address(value: int) -> str:
    return ":".join(f"{(value >> shift) & 0xFF:02X}" for shift in range(40, -1, -8))


class WinRTBackend:
    def __init__(self):
        self._callback: ConnectionCallback | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._devices: dict[str, object] = {}
        self._tokens: dict[str, object] = {}

    async def start(self, on_connection_change: ConnectionCallback) -> None:
        self._callback = on_connection_change
        self._loop = asyncio.get_running_loop()
        await self.paired_devices()

    async def stop(self) -> None:
        for address, device in self._devices.items():
            token = self._tokens.get(address)
            if token is not None:
                try:
                    device.remove_connection_status_changed(token)
                except Exception:  # noqa: BLE001
                    pass
        self._devices.clear()
        self._tokens.clear()

    async def paired_devices(self) -> list[PairedDevice]:
        from winrt.windows.devices.bluetooth import BluetoothConnectionStatus, BluetoothDevice
        from winrt.windows.devices.enumeration import DeviceInformation

        selector = BluetoothDevice.get_device_selector_from_pairing_state(True)
        infos = await DeviceInformation.find_all_async(selector, [PROP_VID, PROP_PID])
        result = []
        for info in infos:
            try:
                device = await BluetoothDevice.from_id_async(info.id)
            except Exception as exc:  # noqa: BLE001
                log.debug("from_id_async failed for %s: %s", info.id, exc)
                continue
            if device is None:
                continue
            address = _format_address(device.bluetooth_address)
            props = info.properties
            vid = props.lookup(PROP_VID) if props.has_key(PROP_VID) else None
            pid = props.lookup(PROP_PID) if props.has_key(PROP_PID) else None
            connected = device.connection_status == BluetoothConnectionStatus.CONNECTED
            result.append(PairedDevice(address, device.name or info.name or address,
                                       int(vid) if vid is not None else None,
                                       int(pid) if pid is not None else None, connected))
            if address not in self._devices:
                self._devices[address] = device
                self._tokens[address] = device.add_connection_status_changed(
                    lambda sender, _args, addr=address: self._status_changed(addr, sender))
        return result

    def _status_changed(self, address: str, sender) -> None:
        from winrt.windows.devices.bluetooth import BluetoothConnectionStatus

        connected = sender.connection_status == BluetoothConnectionStatus.CONNECTED
        if self._loop and self._callback:
            def deliver():
                result = self._callback(address, connected)
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            self._loop.call_soon_threadsafe(deliver)

    async def is_connected(self, address: str) -> bool:
        from winrt.windows.devices.bluetooth import BluetoothConnectionStatus

        device = self._devices.get(address)
        if device is None:
            await self.paired_devices()
            device = self._devices.get(address)
        return bool(device) and device.connection_status == BluetoothConnectionStatus.CONNECTED

    async def connect(self, address: str) -> None:
        raise RuntimeError("Windows: connect the AirPods from the Bluetooth settings")

    async def disconnect(self, address: str) -> None:
        raise RuntimeError("Windows: disconnect the AirPods from the Bluetooth settings")

    async def adapter_powered(self) -> bool:
        try:
            from winrt.windows.devices.bluetooth import BluetoothAdapter

            adapter = await BluetoothAdapter.get_default_async()
            return adapter is not None
        except Exception:  # noqa: BLE001
            return True
