import unittest

from podsdesktop.core.tracker import BleTracker, IdentityFilter
from podsdesktop.protocol import aes, proximity


def irk_pair():
    irk_be = bytes.fromhex("ec0234a357c8ad05341010a60a397d9b")
    return bytes(reversed(irk_be)), "70:81:94:0D:FB:AA"  # resolvable with that IRK


class TrackerHeuristicTests(unittest.TestCase):
    def setUp(self):
        self.tracker = BleTracker(IdentityFilter(model_id=0x2014, rssi_min=-80))

    def test_merges_both_sides(self):
        left = proximity.build(0x2014, primary_left=True, left=80, right=None, case=50)
        right = proximity.build(0x2014, primary_left=False, left=None, right=70, case=None)
        snap = self.tracker.observe("11:11:11:11:11:11", -50, proximity.parse(left), now=1.0)
        self.assertEqual((snap.left_level, snap.right_level, snap.case_level), (80, None, 50))
        snap = self.tracker.observe("22:22:22:22:22:22", -52, proximity.parse(right), now=2.0)
        self.assertEqual((snap.left_level, snap.right_level, snap.case_level), (80, 70, 50))
        self.assertFalse(snap.identified)

    def test_rejects_other_model_weak_signal_and_jumps(self):
        ours = proximity.parse(proximity.build(0x2014, left=80, right=70, case=50))
        self.assertIsNotNone(self.tracker.observe("11:11:11:11:11:11", -50, ours, now=1.0))
        other_model = proximity.parse(proximity.build(0x200E, left=80, right=70, case=50))
        self.assertIsNone(self.tracker.observe("33:33:33:33:33:33", -50, other_model, now=1.5))
        weak = proximity.parse(proximity.build(0x2014, left=80, right=70, case=50))
        self.assertIsNone(self.tracker.observe("44:44:44:44:44:44", -90, weak, now=1.6))
        jump = proximity.parse(proximity.build(0x2014, left=20, right=70, case=50))
        self.assertIsNone(self.tracker.observe("55:55:55:55:55:55", -50, jump, now=1.7))
        # same address: a real drop is accepted (address did not change)
        self.assertIsNotNone(self.tracker.observe("11:11:11:11:11:11", -50, jump, now=1.8))

    def test_disconnected_advert_is_foreign_while_ours_is_connected(self):
        self.tracker.identity.bound_connected = True
        stranger = proximity.parse(proximity.build(0x2014, connection_state=proximity.CONN_DISCONNECTED))
        self.assertIsNone(self.tracker.observe("11:11:11:11:11:11", -40, stranger, now=1.0))
        mine = proximity.parse(proximity.build(0x2014, connection_state=proximity.CONN_MUSIC))
        self.assertIsNotNone(self.tracker.observe("11:11:11:11:11:11", -40, mine, now=1.1))

    def test_lost_after_timeout(self):
        adv = proximity.parse(proximity.build(0x2014))
        self.tracker.observe("11:11:11:11:11:11", -50, adv, now=1.0)
        self.assertFalse(self.tracker.tick(now=5.0))
        self.assertIsNotNone(self.tracker.snapshot)
        self.assertTrue(self.tracker.tick(now=12.0))
        self.assertIsNone(self.tracker.snapshot)

    def test_unchanged_packet_returns_none(self):
        adv = proximity.parse(proximity.build(0x2014, left=80))
        self.assertIsNotNone(self.tracker.observe("11:11:11:11:11:11", -50, adv, now=1.0))
        self.assertIsNone(self.tracker.observe("11:11:11:11:11:11", -55, adv, now=1.5))


class TrackerIdentityTests(unittest.TestCase):
    def test_irk_identifies_and_decrypts(self):
        irk, address = irk_pair()
        key = bytes(range(16))
        plain = bytes([0x00, 0x80 | 63, 61, 12]) + bytes(12)
        packet = proximity.build(0x2014, primary_left=True, left=60, right=60, case=10,
                                 encrypted=aes.encrypt_block(key, plain))
        tracker = BleTracker(IdentityFilter(irk=irk), enc_key=key)
        snap = tracker.observe(address, -45, proximity.parse(packet), now=1.0)
        self.assertTrue(snap.identified)
        self.assertTrue(snap.exact)
        self.assertEqual((snap.left_level, snap.right_level, snap.case_level), (63, 61, 12))
        self.assertTrue(snap.left_charging)
        # a stranger with the very same packet but an unresolvable address is ignored
        self.assertIsNone(tracker.observe("70:81:94:0D:FB:AB", -45, proximity.parse(packet), now=1.1))


if __name__ == "__main__":
    unittest.main()
