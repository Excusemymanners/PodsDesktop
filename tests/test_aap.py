import unittest

from podsdesktop.protocol import aap


class AapTests(unittest.TestCase):
    def test_battery_example_from_docs(self):
        raw = bytes.fromhex("04000400040003020164020104016301010801110201")
        ev = aap.parse(raw)
        self.assertIsInstance(ev, aap.BatteryEvent)
        self.assertEqual(len(ev.components), 3)
        right, left, case = ev.components
        self.assertEqual((right.name, right.level, right.charging), ("right", 100, False))
        self.assertEqual((left.name, left.level, left.charging), ("left", 99, True))
        self.assertEqual((case.name, case.level, case.available), ("case", 17, True))
        self.assertEqual(ev.primary_pod, aap.COMP_RIGHT)

    def test_battery_disconnected_case(self):
        raw = bytes.fromhex("040004000400" "03" "0401500201" "0201510201" "0801000401")
        ev = aap.parse(raw)
        self.assertFalse(ev.get(aap.COMP_CASE).available)
        self.assertEqual(ev.get(aap.COMP_LEFT).level, 80)

    def test_ear_detection(self):
        ev = aap.parse(bytes.fromhex("0400040006000001"))
        self.assertIsInstance(ev, aap.EarEvent)
        self.assertTrue(ev.primary_in_ear)
        self.assertFalse(ev.secondary_in_ear)
        self.assertTrue(ev.any_removed)

    def test_control_noise_mode(self):
        ev = aap.parse(bytes.fromhex("04000400" "0900" "0D" "03000000"))
        self.assertIsInstance(ev, aap.ControlEvent)
        self.assertEqual(ev.identifier, aap.CTL_LISTENING_MODE)
        self.assertEqual(ev.value, aap.MODE_TRANSPARENCY)
        self.assertEqual(ev.name, "Listening mode")

    def test_builders(self):
        self.assertEqual(aap.set_listening_mode(aap.MODE_ANC), bytes.fromhex("040004000900" "0D02000000"))
        self.assertEqual(aap.set_toggle(aap.CTL_CONVERSATIONAL_AWARENESS, True), bytes.fromhex("040004000900" "2801000000"))
        self.assertEqual(aap.set_level(aap.CTL_ADAPTIVE_ANC_STRENGTH, 250), bytes.fromhex("040004000900" "2E64000000"))
        with self.assertRaises(ValueError):
            aap.set_listening_mode(9)

    def test_handshake_ack_and_unknown(self):
        self.assertIsInstance(aap.parse(bytes.fromhex("0100040000")), aap.HandshakeAck)
        ev = aap.parse(bytes.fromhex("04000400" "2b00" "0102"))
        self.assertIsInstance(ev, aap.UnknownEvent)
        self.assertEqual(ev.opcode, 0x2B)
        self.assertIsNone(aap.parse(b"\x00\x01"))

    def test_device_info_example_from_docs(self):
        raw = bytes.fromhex(
            "040004001d0002d5000400416972506f64732050726f004133303438004170706c6520496e632e"
            "0051584e524848595850360036312e313836383034303030323030303030302e323731330036312e"
            "313836383034303030323030303030302e3237313300312e302e3000636f6d2e6170706c652e6163"
            "636573736f72792e757064617465722e6170702e3731004859394c5432454632364a59004833504c"
            "5748444a32364b3000363335373533360089312a6567a5400f84a3ca234947efd40b90d78436ae59"
            "46748d70273e66066a2589300035333935303630363400"
        )
        ev = aap.parse(raw)
        self.assertIsInstance(ev, aap.DeviceInfoEvent)
        self.assertEqual(ev.name, "AirPods Pro")
        self.assertEqual(ev.model_number, "A3048")
        self.assertEqual(ev.manufacturer, "Apple Inc.")
        self.assertEqual(ev.serial, "QXNRHHYXP6")
        self.assertTrue(ev.firmware.startswith("61.18680400"))

    def test_keys_response(self):
        irk = bytes(range(16))
        enc = bytes(range(16, 32))
        raw = (bytes.fromhex("04000400" "3100" "0002")
               + bytes([0x01, 0x00, 0x10, 0x00]) + irk
               + bytes([0x04, 0x00, 0x10, 0x00]) + enc)
        ev = aap.parse(raw)
        self.assertIsInstance(ev, aap.KeysEvent)
        self.assertEqual(ev.irk, irk)
        self.assertEqual(ev.enc_key, enc)

    def test_conversation_level(self):
        ev = aap.parse(bytes.fromhex("04000400" "4b00" "02000103"))
        self.assertIsInstance(ev, aap.ConversationEvent)
        self.assertEqual(ev.level, 3)

    def test_allowed_modes(self):
        self.assertEqual(aap.allowed_modes_from_mask(0x0B), [aap.MODE_OFF, aap.MODE_ANC, aap.MODE_ADAPTIVE])
        self.assertEqual(aap.allowed_modes_from_mask(0), [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
