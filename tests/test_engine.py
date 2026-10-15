"""Engine behaviour without any radio: fake Bluetooth backend, fake media player,
synthetic advertisements and AAP events."""

import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from podsdesktop.core import engine as engine_mod
from podsdesktop.core.bluetooth import PairedDevice
from podsdesktop.core.engine import Engine
from podsdesktop.core.settings import Settings
from podsdesktop.protocol import aap, proximity


class FakeBluetooth:
    def __init__(self, devices):
        self.devices = devices
        self.callback = None
        self.connect_calls = 0

    async def start(self, cb):
        self.callback = cb

    async def stop(self):
        pass

    async def paired_devices(self):
        return list(self.devices)

    async def is_connected(self, address):
        return any(d.address == address and d.connected for d in self.devices)

    async def connect(self, address):
        self.connect_calls += 1

    async def disconnect(self, address):
        pass

    async def adapter_powered(self):
        return False  # keeps the real scanner off


class FakeMedia:
    def __init__(self):
        self.paused = []
        self.resumed = []

    async def pause_playing(self):
        self.paused.append("player")
        return ["player"]

    async def resume(self, handles):
        self.resumed.extend(handles)


def make_engine(tmp: Path, devices=None, keys=None):
    settings = Settings.load(tmp / "settings.json")
    settings.ble_scan = False
    settings.aap = False  # no real L2CAP in tests
    if keys:
        settings.device_address = "CC:08:FA:BC:3F:2F"
        settings.irk, settings.enc_key = keys
    engine = Engine(settings)
    engine.bluetooth = FakeBluetooth(devices or [PairedDevice("CC:08:FA:BC:3F:2F", "Luca's AirPods Pro", 0x004C, 0x2014, False)])
    engine.media = FakeMedia()
    return engine


async def run_engine(engine, body):
    events = []
    engine.subscribe(lambda name, payload: events.append((name, payload)))
    task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.05)
    try:
        await body(events)
    finally:
        engine.stop()
        await asyncio.wait_for(task, 5)
    return events


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name)
        engine_mod.RESUME_DELAY = 0.05

    def tearDown(self):
        self.tmp.cleanup()

    def test_auto_bind_single_apple_device(self):
        engine = make_engine(self.path)

        async def body(events):
            self.assertEqual(engine.settings.device_address, "CC:08:FA:BC:3F:2F")
            self.assertEqual(engine.settings.model_id, 0x2014)
            self.assertEqual(engine.state.display_name, "Luca's AirPods Pro")
            self.assertTrue(any(n == "devices" for n, _ in events))

        asyncio.run(run_engine(engine, body))
        self.assertTrue((self.path / "settings.json").exists())

    def test_ble_adverts_drive_state_lid_and_loss(self):
        engine = make_engine(self.path)

        async def body(events):
            adv = proximity.parse(proximity.build(0x2014, left=80, right=70, case=50, both_in_case=True,
                                                  this_pod_in_case=True, lid_open=True, connection_state=0))
            engine._on_advert("5A:11:11:11:11:11", -50, adv)
            s = engine.state
            self.assertEqual((s.left.level, s.right.level, s.case.level), (80, 70, 50))
            self.assertEqual(s.source, "ble")
            self.assertTrue(s.lid_open and s.both_in_case)
            self.assertIn(("lid", True), events)
            closed = proximity.parse(proximity.build(0x2014, left=80, right=70, case=50, both_in_case=True,
                                                     this_pod_in_case=True, lid_open=False, connection_state=0))
            engine._on_advert("5A:11:11:11:11:11", -50, closed)
            self.assertIn(("lid", False), events)
            # out of range: the tracker expires and the state empties
            engine.tracker.last_seen -= 100
            engine.tracker.tick()
            engine._recompose()
            self.assertFalse(engine.state.has_battery)
            self.assertEqual(engine.state.source, "none")

        asyncio.run(run_engine(engine, body))

    def test_aap_events_take_precedence_and_pause_media(self):
        engine = make_engine(self.path)

        async def body(events):
            await engine._set_connected(True)
            engine._aap.connected = True
            await engine._on_aap_event(aap.parse(bytes.fromhex("04000400040003020164020104016301010801110201")))
            s = engine.state
            self.assertEqual(s.source, "aap")
            self.assertEqual((s.left.level, s.right.level, s.case.level), (99, 100, 17))
            self.assertTrue(s.left.charging)
            # primary pod is the RIGHT one (listed first) -> ear bytes map accordingly
            await engine._on_aap_event(aap.EarEvent(aap.EAR_IN, aap.EAR_IN))
            self.assertTrue(engine.state.both_in_ear)
            await engine._on_aap_event(aap.EarEvent(aap.EAR_IN, aap.EAR_OUT))
            self.assertTrue(engine.state.right.in_ear)
            self.assertFalse(engine.state.left.in_ear)
            await asyncio.sleep(0.05)
            self.assertEqual(engine.media.paused, ["player"])
            self.assertIn(("ears", False), events)
            await engine._on_aap_event(aap.EarEvent(aap.EAR_IN, aap.EAR_IN))
            await asyncio.sleep(0.2)
            self.assertEqual(engine.media.resumed, ["player"])
            # noise mode + allowed modes from control packets
            await engine._on_aap_event(aap.parse(bytes.fromhex("0400040009000D03000000")))
            await engine._on_aap_event(aap.parse(bytes.fromhex("0400040009001A0B000000")))
            self.assertEqual(engine.state.noise_mode, aap.MODE_TRANSPARENCY)
            self.assertEqual(engine.state.allowed_modes, [1, 2, 4])
            # metadata names the device and the keys get stored
            await engine._on_aap_event(aap.DeviceInfoEvent("Luca's AirPods Pro", "A2931", "Apple Inc.", "SER", "6F8"))
            self.assertEqual(engine.state.firmware, "6F8")
            await engine._on_aap_event(aap.KeysEvent(bytes(range(16)), bytes(range(16, 32))))
            self.assertTrue(engine.settings.keys_known)
            self.assertEqual(engine.identity.irk, bytes(range(16)))
            self.assertIn(("keys", True), events)

        asyncio.run(run_engine(engine, body))

    def test_ear_detection_setting_off_does_not_touch_media(self):
        engine = make_engine(self.path)
        engine.settings.ear_detection = False

        async def body(events):
            both = proximity.parse(proximity.build(0x2014, left_in_ear=True, right_in_ear=True))
            one = proximity.parse(proximity.build(0x2014, left_in_ear=True, right_in_ear=False))
            engine._on_advert("5A:11:11:11:11:11", -50, both)
            engine._on_advert("5A:11:11:11:11:11", -50, one)
            await asyncio.sleep(0.05)
            self.assertEqual(engine.media.paused, [])
            self.assertIn(("ears", False), events)

        asyncio.run(run_engine(engine, body))

    def test_low_battery_notified_once(self):
        engine = make_engine(self.path)

        async def body(events):
            for level in (30, 20, 15, 10):
                adv = proximity.parse(proximity.build(0x2014, left=level, right=90, case=50))
                engine._on_advert("5A:11:11:11:11:11", -50, adv)
            lows = [p for n, p in events if n == "low_battery"]
            self.assertEqual(lows, [20])

        asyncio.run(run_engine(engine, body))

    def test_foreign_adverts_ignored_when_keys_known(self):
        irk_be = bytes.fromhex("ec0234a357c8ad05341010a60a397d9b")
        irk = bytes(reversed(irk_be)).hex()
        engine = make_engine(self.path, keys=(irk, bytes(range(16)).hex()))

        async def body(events):
            adv = proximity.parse(proximity.build(0x2014, left=80, right=70, case=50))
            engine._on_advert("5A:11:11:11:11:11", -40, adv)  # not resolvable with our IRK
            self.assertFalse(engine.state.has_battery)
            engine._on_advert("70:81:94:0D:FB:AA", -40, adv)  # resolvable: ours
            self.assertTrue(engine.state.has_battery)

        asyncio.run(run_engine(engine, body))


if __name__ == "__main__":
    unittest.main()
