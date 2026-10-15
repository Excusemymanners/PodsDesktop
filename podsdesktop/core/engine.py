"""The orchestrator: one asyncio loop that owns the radio, the AAP session and the state.

Sources of truth, best first:

1. **AAP session** (Linux, while the pods are connected): exact battery, instant ear events,
   noise mode, device name and firmware. Runs over the classic link, so it is ours by
   construction – no guessing.
2. **BLE advertisements, identified** (any OS, once the device keys are known): the random
   address resolves with the IRK, the payload decrypts to exact levels. Covers the "case
   opened next to the computer" moments when there is no audio link.
3. **BLE advertisements, heuristic** (the AirPodsDesktop way): model match, signal floor and
   continuity checks. Only used until the keys have been learned.

Everything the UI needs arrives through ``subscribe(callback)`` as ``(event, payload)``:
``state`` (DeviceState), ``lid`` (bool), ``ears`` (bool), ``connection`` (bool), ``aap``
(bool), ``keys`` (bool), ``low_battery`` (int), ``devices`` (list), ``notice``/``error`` (str).
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from ..protocol import aap
from ..protocol.models import HEADSET, lookup, lookup_model_number
from .aap_client import AapError, AapSession, aap_supported
from .ble_scanner import BleScanner
from .bluetooth import PairedDevice, create_backend
from .media import create_media_controller
from .settings import Settings
from .state import SOURCE_AAP, SOURCE_BLE, SOURCE_BLE_EXACT, SOURCE_NONE, Component, DeviceState
from .tracker import BleTracker, IdentityFilter

log = logging.getLogger(__name__)

Subscriber = Callable[[str, object], None]
BLE_FRESH = 12.0
RESUME_DELAY = 1.0


@dataclass
class _AapView:
    connected: bool = False
    battery: dict[int, aap.BatteryComponent] = field(default_factory=dict)
    primary_pod: int | None = None
    ear: aap.EarEvent | None = None
    controls: dict[int, tuple[int, int, int, int]] = field(default_factory=dict)
    info: aap.DeviceInfoEvent | None = None

    def clear(self) -> None:
        self.connected = False
        self.battery.clear()
        self.primary_pod = None
        self.ear = None
        self.controls.clear()


class Engine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.state = DeviceState(address=settings.device_address, name=settings.device_name, model_id=settings.model_id)
        self.aap_available = aap_supported()
        self.bluetooth = create_backend()
        self.media = create_media_controller()
        self.identity = IdentityFilter(settings.irk_bytes, settings.model_id, settings.rssi_min)
        self.tracker = BleTracker(self.identity, settings.enc_key_bytes)
        self.scanner = BleScanner(self._on_advert)
        self.devices: list[PairedDevice] = []
        self._aap = _AapView()
        self._session: AapSession | None = None
        self._subscribers: list[Subscriber] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._aap_wakeup: asyncio.Event | None = None
        self._tasks: list[asyncio.Task] = []
        self._paused_players: list[str] = []
        self._resume_task: asyncio.Task | None = None
        self._last_both_in_ear: bool | None = None
        self._last_lid_open: bool | None = None
        self._low_battery_notified = False
        self._aap_backoff = 3.0

    # ------------------------------------------------------------------ pub/sub ----------
    def subscribe(self, callback: Subscriber) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Subscriber) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _emit(self, event: str, payload: object = None) -> None:
        for cb in list(self._subscribers):
            try:
                cb(event, payload)
            except Exception:  # noqa: BLE001
                log.exception("subscriber failed on %s", event)

    def _publish_state(self) -> None:
        self.state.touch()
        self._emit("state", copy.deepcopy(self.state))

    # ------------------------------------------------------------------ lifecycle --------
    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        self._aap_wakeup = asyncio.Event()
        try:
            await self.bluetooth.start(self._on_connection_change)
        except Exception as exc:  # noqa: BLE001
            log.warning("Bluetooth backend unavailable: %s", exc)
            self._emit("error", f"Bluetooth unavailable: {exc}")
        await self.refresh_devices(auto_bind=True)
        self._tasks = [
            asyncio.create_task(self._scan_loop(), name="scan"),
            asyncio.create_task(self._aap_loop(), name="aap"),
            asyncio.create_task(self._tick_loop(), name="tick"),
        ]
        self._publish_state()
        try:
            await self._stop_event.wait()
        finally:
            for task in self._tasks:
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            if self._session:
                await self._session.close()
            await self.scanner.stop()
            await self.bluetooth.stop()

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

    def stop_threadsafe(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self.stop)

    # ------------------------------------------------------------------ devices ----------
    async def refresh_devices(self, auto_bind: bool = False) -> list[PairedDevice]:
        try:
            devices = await self.bluetooth.paired_devices()
        except Exception as exc:  # noqa: BLE001
            log.warning("listing paired devices failed: %s", exc)
            devices = []
        self.devices = [d for d in devices if d.is_apple_audio]
        bound = next((d for d in self.devices if d.address.upper() == (self.settings.device_address or "").upper()), None)
        if bound is None and auto_bind and self.devices:
            bound = next((d for d in self.devices if d.connected), None) if len(self.devices) > 1 else self.devices[0]
            if bound is not None:
                log.info("auto-binding %s (%s)", bound.name, bound.address)
                self.settings.bind(bound.address, bound.name, bound.product_id)
                self.settings.save()
                self._apply_bound_identity()
        if bound is not None:
            self.state.address = bound.address
            if bound.name:
                self.state.name = bound.name
            if bound.product_id is not None:
                self.state.model_id = bound.product_id
            if self.settings.device_name != bound.name or self.settings.model_id != bound.product_id:
                self.settings.device_name, self.settings.model_id = bound.name, bound.product_id
                self.settings.save()
                self.identity.model_id = bound.product_id
            await self._set_connected(bound.connected)
        self._emit("devices", list(self.devices))
        return self.devices

    async def bind(self, address: str | None) -> None:
        device = next((d for d in self.devices if d.address.upper() == (address or "").upper()), None)
        self.settings.bind(address, device.name if device else "", device.product_id if device else None)
        self.settings.save()
        self._aap.clear()
        self.tracker.reset()
        self._apply_bound_identity()
        self.state = DeviceState(address=address, name=self.settings.device_name, model_id=self.settings.model_id)
        self._last_both_in_ear = self._last_lid_open = None
        if self._session:
            await self._session.close()
        await self.refresh_devices()
        self._recompose()
        if self._aap_wakeup:
            self._aap_wakeup.set()

    def _apply_bound_identity(self) -> None:
        self.identity.irk = self.settings.irk_bytes
        self.identity.model_id = self.settings.model_id
        self.identity.rssi_min = self.settings.rssi_min
        self.tracker.enc_key = self.settings.enc_key_bytes

    async def connect_device(self) -> None:
        if not self.settings.device_address:
            self._emit("error", "no device bound")
            return
        try:
            await self.bluetooth.connect(self.settings.device_address)
        except Exception as exc:  # noqa: BLE001
            self._emit("error", str(exc))

    async def disconnect_device(self) -> None:
        if not self.settings.device_address:
            return
        try:
            await self.bluetooth.disconnect(self.settings.device_address)
        except Exception as exc:  # noqa: BLE001
            self._emit("error", str(exc))

    async def _on_connection_change(self, address: str, connected: bool) -> None:
        if (self.settings.device_address or "").upper() != address.upper():
            return
        await self._set_connected(connected)

    async def _set_connected(self, connected: bool) -> None:
        changed = connected != self.state.connected
        self.state.connected = connected
        self.identity.bound_connected = connected
        if not connected and self._aap.connected:
            self._aap.clear()
            if self._session:
                await self._session.close()
        if changed:
            log.info("bound device %s", "connected" if connected else "disconnected")
            self._emit("connection", connected)
            self._recompose()
        if self._aap_wakeup:
            self._aap_wakeup.set()

    # ------------------------------------------------------------------ BLE --------------
    async def _scan_loop(self) -> None:
        while True:
            if not self.settings.ble_scan:
                if self.scanner.running:
                    await self.scanner.stop()
                    self.state.scanning = False
                    self._publish_state()
                await asyncio.sleep(2)
                continue
            try:
                if not await self.bluetooth.adapter_powered():
                    if self.scanner.running or self.state.scanning:
                        await self.scanner.stop()
                        self.state.scanning = False
                        self._publish_state()
                    await asyncio.sleep(5)
                    continue
                if not self.scanner.running:
                    await self.scanner.start()
                    self.state.scanning = True
                    self._publish_state()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("BLE scan problem: %s", exc)
                self.state.scanning = False
                await self.scanner.stop()
                self._publish_state()
                await asyncio.sleep(5)

    def _on_advert(self, address: str, rssi: int | None, adv) -> None:
        log.debug("adv %s rssi=%s %s", address, rssi, adv.desensitized().hex())
        if self.tracker.observe(address, rssi, adv) is not None:
            self._recompose()

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(1)
            if self.tracker.tick():
                log.info("BLE: device out of range")
                self._recompose()

    # ------------------------------------------------------------------ AAP --------------
    async def _aap_loop(self) -> None:
        while True:
            wanted = (self.aap_available and self.settings.aap and self.settings.device_address
                      and self.state.connected)
            if not wanted:
                self._aap_wakeup.clear()
                try:
                    await asyncio.wait_for(self._aap_wakeup.wait(), timeout=15)
                except asyncio.TimeoutError:
                    pass
                continue
            session = AapSession(self.settings.device_address, self._on_aap_event)
            try:
                await session.connect()
                self._session = session
                self._aap.connected = True
                self._aap_backoff = 3.0
                self._emit("aap", True)
                self._recompose()
                await session.run()
            except AapError as exc:
                log.info("AAP: %s", exc)
            except asyncio.CancelledError:
                await session.close()
                raise
            except Exception:  # noqa: BLE001
                log.exception("AAP session crashed")
            finally:
                was_connected = self._aap.connected
                self._session = None
                self._aap.clear()
                if was_connected:
                    self._emit("aap", False)
                    self._recompose()
            await asyncio.sleep(self._aap_backoff)
            self._aap_backoff = min(self._aap_backoff * 1.5, 20.0)

    async def _on_aap_event(self, event: aap.Event) -> None:
        if isinstance(event, aap.BatteryEvent):
            for comp in event.components:
                self._aap.battery[comp.component] = comp
            if event.primary_pod is not None:
                self._aap.primary_pod = event.primary_pod
            self._recompose()
        elif isinstance(event, aap.EarEvent):
            self._aap.ear = event
            self._recompose()
        elif isinstance(event, aap.ControlEvent):
            self._aap.controls[event.identifier] = event.values
            self._recompose()
        elif isinstance(event, aap.DeviceInfoEvent):
            self._aap.info = event
            if event.name:
                self.state.name = event.name
            if event.model_number:
                self.state.model_number = event.model_number
                info = lookup_model_number(event.model_number)
                if info is not None and self.state.model_id is None:
                    self.state.model_id = info.pid
            self.state.firmware = event.firmware
            log.info("AAP device: %s %s fw %s", event.name, event.model_number, event.firmware)
            if not self.settings.keys_known and self._session:
                await self._session.request_keys()
            self._recompose()
        elif isinstance(event, aap.KeysEvent):
            if self.settings.set_keys(event.irk, event.enc_key):
                self.settings.save()
                self._apply_bound_identity()
                log.info("device keys learned: BLE identification is now exact")
                self._emit("keys", True)
        elif isinstance(event, aap.HandshakeAck):
            pass
        elif isinstance(event, aap.UnknownEvent):
            log.debug("AAP unknown opcode 0x%04x: %s", event.opcode, event.payload.hex())

    async def set_noise_mode(self, mode: int) -> None:
        if not self._session:
            self._emit("error", "noise control needs a live AAP session (Linux, pods connected)")
            return
        try:
            await self._session.send(aap.set_listening_mode(mode))
        except AapError as exc:
            self._emit("error", str(exc))
            return
        self.state.noise_mode = mode
        self._publish_state()

    async def set_toggle(self, identifier: int, enabled: bool) -> None:
        await self.set_control(identifier, aap.TOGGLE_ON if enabled else aap.TOGGLE_OFF)

    async def set_control(self, identifier: int, *values: int) -> None:
        if not self._session:
            self._emit("error", "controls need a live AAP session")
            return
        try:
            await self._session.send(aap.control(identifier, *values))
        except AapError as exc:
            self._emit("error", str(exc))
            return
        self._aap.controls[identifier] = tuple(list(values) + [0] * (4 - len(values)))[:4]
        self._recompose()

    async def fetch_keys(self) -> None:
        if not self._session:
            self._emit("error", "keys can only be read over a live AAP session")
            return
        await self._session.request_keys()

    async def apply_settings(self) -> None:
        self.settings.save()
        self._apply_bound_identity()
        if self._aap_wakeup:
            self._aap_wakeup.set()
        self._recompose()

    # ------------------------------------------------------------------ merge ------------
    def _recompose(self) -> None:
        s = self.state
        ble = self.tracker.snapshot
        ble_fresh = ble is not None and (time.monotonic() - ble.seen) <= BLE_FRESH
        s.aap_connected = self._aap.connected
        s.rssi = ble.rssi if ble_fresh else None
        if s.model_id is None and ble is not None:
            s.model_id = ble.model_id
        headset = s.model is not None and s.model.kind == HEADSET

        if self._aap.connected and self._aap.battery:
            s.source = SOURCE_AAP
            s.left = self._component_from_aap(aap.COMP_HEADSET if headset else aap.COMP_LEFT)
            s.right = Component() if headset else self._component_from_aap(aap.COMP_RIGHT)
            s.case = self._component_from_aap(aap.COMP_CASE)
            if not s.case.available and ble_fresh and ble.case_level is not None:
                s.case = Component(ble.case_level, ble.case_charging, False, True, ble.exact)
            ear = self._aap.ear
            if ear is not None:
                primary_left = self._aap.primary_pod != aap.COMP_RIGHT
                left_in, right_in = (ear.primary_in_ear, ear.secondary_in_ear) if primary_left else (ear.secondary_in_ear, ear.primary_in_ear)
                s.left.in_ear, s.right.in_ear = left_in, (False if headset else right_in)
                s.both_in_case = ear.primary == aap.EAR_IN_CASE and ear.secondary == aap.EAR_IN_CASE
            elif ble_fresh:
                s.left.in_ear, s.right.in_ear, s.both_in_case = ble.left_in_ear, ble.right_in_ear, ble.both_in_case
        elif ble_fresh:
            s.source = SOURCE_BLE_EXACT if ble.exact else SOURCE_BLE
            s.left = Component(ble.left_level, ble.left_charging, ble.left_in_ear, ble.left_level is not None, ble.exact)
            s.right = Component(ble.right_level, ble.right_charging, ble.right_in_ear, ble.right_level is not None, ble.exact)
            s.case = Component(ble.case_level, ble.case_charging, False, ble.case_level is not None, ble.exact)
            s.both_in_case = ble.both_in_case
        else:
            s.source = SOURCE_NONE
            s.left, s.right, s.case = Component(), Component(), Component()
            s.both_in_case = False
        s.lid_open = ble.lid_open if ble_fresh else None

        controls = self._aap.controls
        mode = controls.get(aap.CTL_LISTENING_MODE)
        s.noise_mode = mode[0] if mode and mode[0] in aap.MODE_NAMES else (s.noise_mode if self._aap.connected else None)
        allowed = controls.get(aap.CTL_LISTENING_MODE_CONFIGS)
        s.allowed_modes = aap.allowed_modes_from_mask(allowed[0]) if allowed else [1, 2, 3, 4]
        ca = controls.get(aap.CTL_CONVERSATIONAL_AWARENESS)
        s.conversational_awareness = (ca[0] == aap.TOGGLE_ON) if ca else None
        s.controls = {k: list(v) for k, v in controls.items()}

        self._publish_state()
        self._detect_transitions()

    def _component_from_aap(self, component: int) -> Component:
        comp = self._aap.battery.get(component)
        if comp is None or not comp.available:
            return Component()
        return Component(comp.level, comp.charging, False, True, True)

    def _detect_transitions(self) -> None:
        s = self.state
        lid_open = bool(s.lid_open and s.both_in_case) if s.lid_open is not None else False
        if lid_open != bool(self._last_lid_open):
            self._last_lid_open = lid_open
            if s.source != SOURCE_NONE or not lid_open:
                self._emit("lid", lid_open)

        if s.source == SOURCE_NONE:
            self._last_both_in_ear = None
        else:
            both = s.both_in_ear
            if self._last_both_in_ear is not None and both != self._last_both_in_ear:
                self._emit("ears", both)
                if self.settings.ear_detection and self._loop:
                    self._loop.create_task(self._handle_ears(both))
            self._last_both_in_ear = both

        level = s.min_pod_level()
        threshold = self.settings.low_battery_threshold
        if level is not None:
            if level <= threshold and not self._low_battery_notified:
                self._low_battery_notified = True
                self._emit("low_battery", level)
            elif level > threshold + 10:
                self._low_battery_notified = False

    async def _handle_ears(self, both_in_ear: bool) -> None:
        if both_in_ear:
            if self._paused_players:
                if self._resume_task and not self._resume_task.done():
                    return
                self._resume_task = asyncio.create_task(self._resume_later())
        else:
            if self._resume_task and not self._resume_task.done():
                self._resume_task.cancel()
            paused = await self.media.pause_playing()
            if paused:
                self._paused_players = paused

    async def _resume_later(self) -> None:
        await asyncio.sleep(RESUME_DELAY)
        if self.state.both_in_ear and self._paused_players:
            handles, self._paused_players = self._paused_players, []
            await self.media.resume(handles)
