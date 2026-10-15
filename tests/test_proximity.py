import unittest

from podsdesktop.protocol import aes, proximity


# Sanitized captures from AirPods 5 (AirPodsDesktop test-suite), payload zeroed.
CAPTURED_LEFT = bytes.fromhex("0719013020" "35aaba3200" "05" + "00" * 16)
CAPTURED_RIGHT = bytes.fromhex("0719013020" "55aaba3200" "05" + "00" * 16)


class ProximityParseTests(unittest.TestCase):
    def test_rejects_other_messages(self):
        self.assertIsNone(proximity.parse(b""))
        self.assertIsNone(proximity.parse(bytes([0x10, 0x05, 0, 0, 0, 0, 0])))
        bad_length = bytearray(CAPTURED_LEFT)
        bad_length[1] = 24
        self.assertIsNone(proximity.parse(bytes(bad_length)))
        self.assertIsNone(proximity.parse(CAPTURED_LEFT[:-1]))

    def test_captured_airpods5_both_sides(self):
        for raw, primary_left in ((CAPTURED_LEFT, True), (CAPTURED_RIGHT, False)):
            adv = proximity.parse(raw)
            self.assertIsNotNone(adv)
            self.assertEqual(adv.model_id, 0x2030)
            self.assertEqual(adv.model.name, "AirPods 5")
            self.assertEqual(adv.primary_left, primary_left)
            self.assertEqual((adv.left_battery, adv.right_battery, adv.case_battery), (100, 100, 100))
            self.assertTrue(adv.left_charging and adv.right_charging)
            self.assertFalse(adv.case_charging)
            self.assertFalse(adv.left_in_ear or adv.right_in_ear)
            self.assertTrue(adv.both_in_case)
            self.assertTrue(adv.lid_open)
            self.assertEqual(adv.lid_counter, 2)
            self.assertEqual(adv.connection_state, proximity.CONN_MUSIC)
            self.assertEqual(adv.desensitized()[11:], bytes(16))

    def test_build_and_parse_roundtrip_both_sides(self):
        for primary_left in (True, False):
            raw = proximity.build(
                0x2014, primary_left=primary_left, left=80, right=70, case=50,
                left_charging=False, right_charging=True, left_in_ear=True, right_in_ear=False,
                lid_open=False, both_in_case=False, connection_state=proximity.CONN_IDLE,
            )
            adv = proximity.parse(raw)
            self.assertEqual(adv.primary_left, primary_left)
            self.assertEqual((adv.left_battery, adv.right_battery, adv.case_battery), (80, 70, 50))
            self.assertTrue(adv.right_charging)
            self.assertFalse(adv.left_charging)
            self.assertTrue(adv.left_in_ear)
            self.assertFalse(adv.right_in_ear)  # charging wins over the ear bit
            self.assertIsNone(adv.lid_open)      # nobody is in the case, lid bit is noise

    def test_unknown_battery_nibble(self):
        adv = proximity.parse(proximity.build(0x200E, left=None, right=30, case=None))
        self.assertIsNone(adv.left_battery)
        self.assertEqual(adv.right_battery, 30)
        self.assertIsNone(adv.case_battery)

    def test_decrypt_exact_levels(self):
        key = bytes.fromhex("00112233445566778899aabbccddeeff")
        # byte1 = this pod (charging, 87 %), byte2 = other pod (42 %), byte3 = case (unknown)
        plain = bytes([0x01, 0x80 | 87, 42, 0x7F]) + bytes(12)
        cipher = aes.encrypt_block(key, plain)
        adv = proximity.parse(proximity.build(0x2014, primary_left=False, encrypted=cipher))
        exact = adv.decrypt(key)
        self.assertEqual((exact.left, exact.right, exact.case), (42, 87, None))
        self.assertTrue(exact.right_charging)
        self.assertFalse(exact.left_charging)

    def test_from_manufacturer_data(self):
        self.assertIsNone(proximity.from_manufacturer_data({0x0059: b"\x01"}))
        self.assertIsNotNone(proximity.from_manufacturer_data({0x004C: CAPTURED_LEFT}))


if __name__ == "__main__":
    unittest.main()
