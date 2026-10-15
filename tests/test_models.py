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
