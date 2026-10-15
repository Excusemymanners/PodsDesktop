import unittest

from podsdesktop.protocol import aes


class AesTests(unittest.TestCase):
    def test_fips197_vector(self):
        key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
        plain = bytes.fromhex("00112233445566778899aabbccddeeff")
        cipher = bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")
        self.assertEqual(aes.encrypt_block(key, plain), cipher)
        self.assertEqual(aes.decrypt_block(key, cipher), plain)

    def test_ble_ah_core_spec_sample(self):
        # Bluetooth Core, Vol 3 Part H, Appendix D.7 (ah random address hash)
        irk = bytes.fromhex("ec0234a357c8ad05341010a60a397d9b")
        self.assertEqual(aes.ble_ah(irk, bytes.fromhex("708194")), bytes.fromhex("0dfbaa"))

    def test_resolve_rpa_with_transmitted_key_order(self):
        irk_big_endian = bytes.fromhex("ec0234a357c8ad05341010a60a397d9b")
        irk_as_transmitted = bytes(reversed(irk_big_endian))
        self.assertTrue(aes.resolve_rpa(irk_as_transmitted, "70:81:94:0D:FB:AA"))
        self.assertFalse(aes.resolve_rpa(irk_as_transmitted, "70:81:94:0D:FB:AB"))
        # not a resolvable private address (top bits 0b11 = static random)
        self.assertFalse(aes.resolve_rpa(irk_as_transmitted, "F0:81:94:0D:FB:AA"))
        self.assertFalse(aes.resolve_rpa(b"\0" * 15, "70:81:94:0D:FB:AA"))
        self.assertFalse(aes.resolve_rpa(irk_as_transmitted, "garbage"))

    def test_payload_roundtrip(self):
        key = bytes(range(16))
        plain = bytes.fromhex("01e4a2117f7f7f7f7f7f7f7f7f7f7f7f")
        cipher = aes.encrypt_block(key, plain)
        self.assertEqual(aes.decrypt_proximity_payload(key, cipher), plain)


if __name__ == "__main__":
    unittest.main()
