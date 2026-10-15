import unittest

from podsdesktop.protocol import models


class ModelTests(unittest.TestCase):
    def test_known_models(self):
        self.assertEqual(models.lookup(0x2014).name, "AirPods Pro 2")
        self.assertEqual(models.lookup(0x202D).name, "AirPods Max 2")
        self.assertEqual(models.lookup(0x202D).kind, models.HEADSET)
        self.assertEqual(models.lookup(0x2030).name, "AirPods 5")
        self.assertEqual(models.lookup(0x2036).name, "AirPods 5")

    def test_unknown_in_range_is_generic_not_dropped(self):
        info = models.lookup(0x2FFF)
        self.assertFalse(info.is_known)
        self.assertIn("0x2FFF", info.name)
        self.assertTrue(models.is_apple_audio_pid(0x2FFF))
        self.assertFalse(models.is_apple_audio_pid(0x1234))

    def test_model_number(self):
        self.assertEqual(models.lookup_model_number("A3048").pid, 0x2024)
        self.assertIsNone(models.lookup_model_number("X0000"))


if __name__ == "__main__":
    unittest.main()


class WindowsPnpTests(unittest.TestCase):
    def test_parse_pnp_ids(self):
        from podsdesktop.core.bluetooth_windows import format_address, parse_pnp_ids

        text = ("BTHENUM\\{0000110B-0000-1000-8000-00805F9B34FB}_VID&0001004C_PID&202D\\8&2E6A9A6&0&CC08FABC3F2F_C00000000\n"
                "BTHENUM\\{0000111E-0000-1000-8000-00805F9B34FB}_VID&0001004C_PID&202D\\8&2E6A9A6&0&CC08FABC3F2F_C00000000\n"
                "USB\\VID_8087&PID_0033\\5&1234\n")
        self.assertEqual(parse_pnp_ids(text), {"CC:08:FA:BC:3F:2F": (0x004C, 0x202D)})
        self.assertEqual(format_address(0xCC08FABC3F2F), "CC:08:FA:BC:3F:2F")

    def test_name_fallback_without_device_id(self):
        from podsdesktop.core.bluetooth import PairedDevice

        self.assertTrue(PairedDevice("00:11:22:33:44:55", "Luca's AirPods Pro", None, None, False).is_apple_audio)
        self.assertFalse(PairedDevice("00:11:22:33:44:55", "JBL Flip", None, None, False).is_apple_audio)
        self.assertFalse(PairedDevice("00:11:22:33:44:55", "AirPods", 0x1234, 0x2014, False).is_apple_audio)
