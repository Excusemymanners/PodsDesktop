"""Windows backend through WinRT (the ``winrt-Windows.Devices.*`` packages that bleak installs).

Paired devices are enumerated with ``DeviceInformation``; vendor/product ids are read from the
device properties and, when those are missing, from the PnP instance ids
(``BTHENUM\\{...}_VID&0001004C_PID&2014\\...&CC08FABC3F2F_...``) via PowerShell. Connection status
changes come from ``BluetoothDevice.ConnectionStatusChanged``. Connecting on demand has no public
WinRT API, so that is left to the system settings.
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import time

from .bluetooth import ConnectionCallback, PairedDevice

log = logging.getLogger(__name__)

PROP_VID = "System.DeviceInterface.Bluetooth.VendorId"
PROP_PID = "System.DeviceInterface.Bluetooth.ProductId"
PNP_RE = re.compile(r"VID&0001([0-9A-Fa-f]{4})_PID&([0-9A-Fa-f]{4})\\[^\\]*?&([0-9A-Fa-f]{12})(?:_|$)", re.M)


def format_address(value: int) -> str:
    return ":".join(f"{(value >> shift) & 0xFF:02X}" for shift in range(40, -1, -8))


def parse_pnp_ids(text: str) -> dict[str, tuple[int, int]]:
    """``{"CC:08:FA:BC:3F:2F": (0x004C, 0x2014)}`` from PnP instance ids (first hit per address)."""
    table: dict[str, tuple[int, int]] = {}
    for match in PNP_RE.finditer(text):
        vid, pid, raw = int(match.group(1), 16), int(match.group(2), 16), match.group(3).upper()
        address = ":".join(raw[i : i + 2] for i in range(0, 12, 2))
        table.setdefault(address, (vid, pid))
    return table


def _unbox_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return int(value)
    try:
        from winrt import system
    except ImportError:
        return None
    for name in ("unbox_uint16", "unbox_int32", "unbox_uint32", "unbox_int16", "unbox_uint8", "unbox_int64"):
        fn = getattr(system, name, None)
        if fn is None:
            continue
        try:
            return int(fn(value))
        except Exception:  # noqa: BLE001
            continue
    return None


def _property(info, key: str) -> int | None:
    try:
        props = info.properties
        if key in props:
            return _unbox_int(props[key])
    except Exception:  # noqa: BLE001
        pass
    try:
        if info.properties.has_key(key):
            return _unbox_int(info.properties.lookup(key))
    except Exception:  # noqa: BLE001
        pass
    return None


class WinRTBackend:
    def __init__(self):
        self._callback: ConnectionCallback | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._devices: dict[str, object] = {}
        self._tokens: dict[str, object] = {}
        self._pnp: dict[str, tuple[int, int]] = {}
        self._pnp_time = 0.0

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

    async def _pnp_table(self) -> dict[str, tuple[int, int]]:
        if time.monotonic() - self._pnp_time < 60 and self._pnp:
            return self._pnp

        def run() -> str:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                     "Get-PnpDevice -PresentOnly:$false | ForEach-Object InstanceId"],
                    capture_output=True, text=True, timeout=20, creationflags=flags)
                return out.stdout
            except (OSError, subprocess.SubprocessError) as exc:
                log.debug("Get-PnpDevice failed: %s", exc)
                return ""

        self._pnp = parse_pnp_ids(await asyncio.to_thread(run))
        self._pnp_time = time.monotonic()
        return self._pnp

    async def paired_devices(self) -> list[PairedDevice]:
        from winrt.windows.devices.bluetooth import BluetoothConnectionStatus, BluetoothDevice
        from winrt.windows.devices.enumeration import DeviceInformation

        selector = BluetoothDevice.get_device_selector_from_pairing_state(True)
        finder = getattr(DeviceInformation, "find_all_async_aqs_filter_and_additional_properties", None)
        if finder is not None:
            infos = await finder(selector, [PROP_VID, PROP_PID])
        else:  # older pywinrt releases used overloads on one name
            infos = await DeviceInformation.find_all_async(selector, [PROP_VID, PROP_PID])
        result = []
        pnp = None
        for info in infos:
            try:
                device = await BluetoothDevice.from_id_async(info.id)
            except Exception as exc:  # noqa: BLE001
                log.debug("from_id_async failed for %s: %s", info.id, exc)
                continue
            if device is None:
                continue
            address = format_address(device.bluetooth_address)
            vid, pid = _property(info, PROP_VID), _property(info, PROP_PID)
            if vid is None or pid is None:
                if pnp is None:
                    pnp = await self._pnp_table()
                vid, pid = pnp.get(address, (vid, pid))
            connected = device.connection_status == BluetoothConnectionStatus.CONNECTED
            result.append(PairedDevice(address, device.name or info.name or address, vid, pid, connected))
            if address not in self._devices:
                self._devices[address] = device
                try:
                    self._tokens[address] = device.add_connection_status_changed(
                        lambda sender, _args, addr=address: self._status_changed(addr, sender))
                except Exception as exc:  # noqa: BLE001
                    log.debug("connection watch failed for %s: %s", address, exc)
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
        from ..core.system import open_bluetooth_settings

        open_bluetooth_settings()
        raise RuntimeError("Windows: connect the AirPods from the Bluetooth settings that just opened")

    async def disconnect(self, address: str) -> None:
        raise RuntimeError("Windows: disconnect the AirPods from the Bluetooth settings")

    async def adapter_powered(self) -> bool:
        try:
            from winrt.windows.devices.bluetooth import BluetoothAdapter
            from winrt.windows.devices.radios import RadioState

            adapter = await BluetoothAdapter.get_default_async()
            if adapter is None:
                return False
            radio = await adapter.get_radio_async()
            return radio is None or radio.state == RadioState.ON
        except ImportError:
            try:
                from winrt.windows.devices.bluetooth import BluetoothAdapter

                return (await BluetoothAdapter.get_default_async()) is not None
            except Exception:  # noqa: BLE001
                return True
        except Exception:  # noqa: BLE001
            return True

    async def power_on(self) -> None:
        try:
            from winrt.windows.devices.bluetooth import BluetoothAdapter
            from winrt.windows.devices.radios import RadioState

            adapter = await BluetoothAdapter.get_default_async()
            radio = await adapter.get_radio_async() if adapter else None
            if radio is not None:
                await radio.set_state_async(RadioState.ON)
                return
        except Exception as exc:  # noqa: BLE001
            log.debug("radio power on failed: %s", exc)
        from ..core.system import open_bluetooth_settings

        open_bluetooth_settings()
