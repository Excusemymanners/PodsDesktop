"""BlueZ over the system D-Bus, using dbus-fast (no bluetoothctl shelling out)."""

from __future__ import annotations

import asyncio
import logging
import re

from dbus_fast import BusType, Message, MessageType
from dbus_fast.aio import MessageBus

from .bluetooth import ConnectionCallback, PairedDevice

log = logging.getLogger(__name__)

BLUEZ = "org.bluez"
DEVICE_IFACE = "org.bluez.Device1"
ADAPTER_IFACE = "org.bluez.Adapter1"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
MODALIAS_RE = re.compile(r"v([0-9A-Fa-f]{4})p([0-9A-Fa-f]{4})")


def _unwrap(value):
    return value.value if hasattr(value, "value") else value


def device_path(address: str, adapter: str = "/org/bluez/hci0") -> str:
    return f"{adapter}/dev_{address.upper().replace(':', '_')}"


class BlueZBackend:
    def __init__(self):
        self._bus: MessageBus | None = None
        self._callback: ConnectionCallback | None = None
        self._paths: dict[str, str] = {}  # device path -> address

    async def _ensure_bus(self) -> MessageBus:
        if self._bus is None:
            self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        return self._bus

    async def start(self, on_connection_change: ConnectionCallback) -> None:
        self._callback = on_connection_change
        bus = await self._ensure_bus()
        rule = f"type='signal',interface='{PROPS_IFACE}',member='PropertiesChanged',arg0='{DEVICE_IFACE}'"
        await bus.call(Message(destination="org.freedesktop.DBus", path="/org/freedesktop/DBus",
                               interface="org.freedesktop.DBus", member="AddMatch", signature="s", body=[rule]))
        bus.add_message_handler(self._on_message)
        await self.paired_devices()  # fills the path map

    async def stop(self) -> None:
        if self._bus is not None:
            try:
                self._bus.remove_message_handler(self._on_message)
                self._bus.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self._bus = None

    def _on_message(self, msg: Message):
        if msg.message_type != MessageType.SIGNAL or msg.member != "PropertiesChanged":
            return
        if not msg.body or msg.body[0] != DEVICE_IFACE:
            return
        changed = msg.body[1]
        if "Connected" not in changed:
            return
        address = self._paths.get(msg.path) or msg.path.rsplit("dev_", 1)[-1].replace("_", ":")
        connected = bool(_unwrap(changed["Connected"]))
        log.info("BlueZ: %s %s", address, "connected" if connected else "disconnected")
        if self._callback:
            result = self._callback(address, connected)
            if asyncio.iscoroutine(result):
                asyncio.ensure_future(result)

    async def _managed_objects(self) -> dict:
        bus = await self._ensure_bus()
        reply = await bus.call(Message(destination=BLUEZ, path="/", interface="org.freedesktop.DBus.ObjectManager",
                                       member="GetManagedObjects"))
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"BlueZ unavailable: {reply.body}")
        return reply.body[0]

    async def paired_devices(self) -> list[PairedDevice]:
        devices = []
        for path, interfaces in (await self._managed_objects()).items():
            props = interfaces.get(DEVICE_IFACE)
            if not props:
                continue
            props = {k: _unwrap(v) for k, v in props.items()}
            if not props.get("Paired"):
                continue
            vendor = product = None
            match = MODALIAS_RE.search(props.get("Modalias", "") or "")
            if match:
                vendor, product = int(match.group(1), 16), int(match.group(2), 16)
            address = props.get("Address", "")
            self._paths[path] = address
            devices.append(PairedDevice(address, props.get("Alias") or props.get("Name") or address,
                                        vendor, product, bool(props.get("Connected"))))
        return devices

    async def _get_property(self, path: str, iface: str, name: str):
        bus = await self._ensure_bus()
        reply = await bus.call(Message(destination=BLUEZ, path=path, interface=PROPS_IFACE, member="Get",
                                       signature="ss", body=[iface, name]))
        if reply.message_type == MessageType.ERROR:
            return None
        return _unwrap(reply.body[0])

    def _path_for(self, address: str) -> str:
        for path, addr in self._paths.items():
            if addr.upper() == address.upper():
                return path
        return device_path(address)

    async def is_connected(self, address: str) -> bool:
        return bool(await self._get_property(self._path_for(address), DEVICE_IFACE, "Connected"))

    async def _device_call(self, address: str, member: str) -> None:
        bus = await self._ensure_bus()
        reply = await bus.call(Message(destination=BLUEZ, path=self._path_for(address), interface=DEVICE_IFACE, member=member))
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"{member} failed: {reply.body[0] if reply.body else reply.error_name}")

    async def connect(self, address: str) -> None:
        await self._device_call(address, "Connect")

    async def disconnect(self, address: str) -> None:
        await self._device_call(address, "Disconnect")

    async def adapter_powered(self) -> bool:
        try:
            objects = await self._managed_objects()
        except RuntimeError:
            return False
        for interfaces in objects.values():
            adapter = interfaces.get(ADAPTER_IFACE)
            if adapter and _unwrap(adapter.get("Powered")):
                return True
        return False
