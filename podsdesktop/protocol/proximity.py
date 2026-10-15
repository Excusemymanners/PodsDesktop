"""Apple Continuity *Proximity Pairing* advertisement (manufacturer data, type 0x07).

Layout of the 27 bytes Apple audio devices broadcast (all AirPods, most Beats)::

    0   0x07           message type: proximity pairing
    1   0x19           remaining length (25)
    2   0x01           0x01 = paired device status, 0x00 = pairing-mode packet (other layout)
    3-4 model id       little-endian, same value as the classic Bluetooth product id
    5   status         bit1 this pod in ear, bit2 both pods in case, bit3 other pod in ear,
                       bit4 one pod in case, bit5 broadcasting pod is the LEFT one,
                       bit6 broadcasting pod is in the case
    6   pod batteries  low nibble: broadcasting pod, high nibble: the other pod (0-10 => x10 %,
                       15 = unknown)
    7   case + flags   low nibble: case battery; bit4 this pod charging, bit5 other pod
                       charging, bit6 case charging
    8   lid            bits0-2 open/close counter, bit3 1 = lid closed
    9   colour
    10  connection     0x00 disconnected, 0x04 idle, 0x05 music, 0x06 call, 0x07 ringing,
                       0x09 hanging up
    11-26 payload      16 bytes, AES-128 encrypted with the device's ENC_KEY; holds the
                       exact battery levels (see :meth:`ProximityAdvert.decrypt`)

The packet never says "left" or "right": it says "me" and "the other one", plus one bit
that tells which side "me" is. Everything below resolves that into left/right.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import aes
from .models import APPLE_VENDOR_ID, HEADSET, ModelInfo, lookup

PACKET_TYPE = 0x07
PACKET_LENGTH = 27
PAYLOAD_LENGTH = 16

COLORS = {
    0x00: "White", 0x01: "Black", 0x02: "Red", 0x03: "Blue", 0x04: "Pink", 0x05: "Gray",
    0x06: "Silver", 0x07: "Gold", 0x08: "Rose Gold", 0x09: "Space Gray", 0x0A: "Dark Blue",
    0x0B: "Light Blue", 0x0C: "Yellow",
}

CONN_DISCONNECTED = 0x00
CONN_IDLE = 0x04
CONN_MUSIC = 0x05
CONN_CALL = 0x06
CONN_RINGING = 0x07
CONN_HANGING_UP = 0x09
CONNECTION_STATES = {
    CONN_DISCONNECTED: "disconnected", CONN_IDLE: "idle", CONN_MUSIC: "music",
    CONN_CALL: "call", CONN_RINGING: "ringing", CONN_HANGING_UP: "hanging up",
}

UNAVAILABLE_LEVEL = 0x7F


def _nibble_level(nibble: int) -> int | None:
    return nibble * 10 if 0 <= nibble <= 10 else None


def is_proximity_pairing(data: bytes) -> bool:
    return (
        len(data) == PACKET_LENGTH
        and data[0] == PACKET_TYPE
        and data[1] == PACKET_LENGTH - 2
    )


@dataclass(frozen=True)
class ExactBattery:
    """Battery levels decoded from the encrypted payload (1 % resolution)."""

    left: int | None
    right: int | None
    case: int | None
    left_charging: bool
    right_charging: bool
    case_charging: bool


@dataclass(frozen=True)
class ProximityAdvert:
    raw: bytes
    model_id: int
    paired: bool
    primary_left: bool          # the broadcasting pod is the left one
    this_pod_in_case: bool
    one_pod_in_case: bool
    both_in_case: bool
    left_in_ear: bool
    right_in_ear: bool
    left_battery: int | None    # 0-100 in steps of 10, None = unknown
    right_battery: int | None
    case_battery: int | None
    left_charging: bool
    right_charging: bool
    case_charging: bool
    lid_open: bool | None       # only meaningful while a pod sits in the case
    lid_counter: int
    color: int
    connection_state: int
    encrypted: bytes

    # ---- derived -------------------------------------------------------------------
    @property
    def model(self) -> ModelInfo:
        return lookup(self.model_id)

    @property
    def is_headset(self) -> bool:
        return self.model.kind == HEADSET

    @property
    def color_name(self) -> str:
        return COLORS.get(self.color, f"0x{self.color:02X}")

    @property
    def connection_name(self) -> str:
        return CONNECTION_STATES.get(self.connection_state, f"0x{self.connection_state:02X}")

    @property
    def is_connected_somewhere(self) -> bool:
        return self.connection_state != CONN_DISCONNECTED

    @property
    def both_in_ear(self) -> bool:
        return self.left_in_ear and self.right_in_ear

    def desensitized(self) -> bytes:
        """The packet with the encrypted (possibly identifying) tail zeroed, for logs."""
        return self.raw[: PACKET_LENGTH - PAYLOAD_LENGTH] + bytes(PAYLOAD_LENGTH)

    def decrypt(self, enc_key: bytes) -> ExactBattery:
        """Exact battery levels from the encrypted tail, using the AAP ``ENC_KEY``.

        Decrypted layout: byte 1 = broadcasting pod, byte 2 = other pod, byte 3 = case;
        bit 7 = charging, bits 0-6 = level (0x7F = unavailable). For a headset the single
        battery is in whichever slot is not 0x7F.
        """
        plain = aes.decrypt_proximity_payload(enc_key, self.encrypted)

        def split(byte: int) -> tuple[int | None, bool]:
            level = byte & 0x7F
            return (None if level == UNAVAILABLE_LEVEL else min(level, 100)), bool(byte & 0x80)

        this_level, this_chg = split(plain[1])
        other_level, other_chg = split(plain[2])
        case_level, case_chg = split(plain[3])
        if self.primary_left:
            left, right = (this_level, this_chg), (other_level, other_chg)
        else:
            left, right = (other_level, other_chg), (this_level, this_chg)
        return ExactBattery(left[0], right[0], case_level, left[1], right[1], case_chg)


def parse(data: bytes) -> ProximityAdvert | None:
    """Parse the Apple manufacturer-data bytes; ``None`` when it is not a pairing packet."""
    if not is_proximity_pairing(data):
        return None
    paired = data[2] == 0x01
    model_id = data[3] | (data[4] << 8)
    status = data[5]
    pods = data[6]
    case_flags = data[7]
    lid = data[8]

    primary_left = bool(status & 0x20)
    this_pod_in_case = bool(status & 0x40)
    flipped = not primary_left

    this_level = _nibble_level(pods & 0x0F)
    other_level = _nibble_level(pods >> 4)
    this_charging = bool(case_flags & 0x10)
    other_charging = bool(case_flags & 0x20)
    if primary_left:
        left_level, right_level = this_level, other_level
        left_charging, right_charging = this_charging, other_charging
    else:
        left_level, right_level = other_level, this_level
        left_charging, right_charging = other_charging, this_charging

    # In-ear bits follow the broadcasting pod, and swap again when that pod is in the case.
    xor = flipped ^ this_pod_in_case
    bit_this, bit_other = bool(status & 0x02), bool(status & 0x08)
    left_in_ear, right_in_ear = (bit_other, bit_this) if xor else (bit_this, bit_other)
    # A charging pod is in the case, whatever the ear bit says (it is set while docked).
    left_in_ear = left_in_ear and not left_charging
    right_in_ear = right_in_ear and not right_charging

    return ProximityAdvert(
        raw=bytes(data),
        model_id=model_id,
        paired=paired,
        primary_left=primary_left,
        this_pod_in_case=this_pod_in_case,
        one_pod_in_case=bool(status & 0x10),
        both_in_case=bool(status & 0x04),
        left_in_ear=left_in_ear,
        right_in_ear=right_in_ear,
        left_battery=left_level,
        right_battery=right_level,
        case_battery=_nibble_level(case_flags & 0x0F),
        left_charging=left_charging,
        right_charging=right_charging,
        case_charging=bool(case_flags & 0x40),
        lid_open=(not bool(lid & 0x08)) if (this_pod_in_case or status & 0x04) else None,
        lid_counter=lid & 0x07,
        color=data[9],
        connection_state=data[10],
        encrypted=bytes(data[11:27]),
    )


def from_manufacturer_data(manufacturer_data: dict[int, bytes]) -> ProximityAdvert | None:
    """Convenience for scanners that hand over ``{company_id: bytes}``."""
    data = manufacturer_data.get(APPLE_VENDOR_ID)
    return parse(data) if data is not None else None


def build(
    model_id: int,
    *,
    primary_left: bool = True,
    left: int | None = 100,
    right: int | None = 100,
    case: int | None = 100,
    left_charging: bool = False,
    right_charging: bool = False,
    case_charging: bool = False,
    left_in_ear: bool = False,
    right_in_ear: bool = False,
    both_in_case: bool = False,
    this_pod_in_case: bool = False,
    lid_open: bool = True,
    lid_counter: int = 0,
    color: int = 0,
    connection_state: int = CONN_IDLE,
    encrypted: bytes = bytes(16),
) -> bytes:
    """Build a packet (tests, simulator, documentation). Levels are 0-100 or ``None``."""

    def nib(level: int | None) -> int:
        return 0x0F if level is None else max(0, min(10, round(level / 10)))

    status = 0
    if primary_left:
        status |= 0x20
    if this_pod_in_case:
        status |= 0x40
    if both_in_case:
        status |= 0x04
    flipped = not primary_left
    xor = flipped ^ this_pod_in_case
    bit_this, bit_other = (right_in_ear, left_in_ear) if xor else (left_in_ear, right_in_ear)
    if bit_this:
        status |= 0x02
    if bit_other:
        status |= 0x08
    this_level, other_level = (left, right) if primary_left else (right, left)
    this_chg, other_chg = (left_charging, right_charging) if primary_left else (right_charging, left_charging)
    pods = nib(this_level) | (nib(other_level) << 4)
    case_flags = nib(case) | (0x10 if this_chg else 0) | (0x20 if other_chg else 0) | (0x40 if case_charging else 0)
    lid = (lid_counter & 0x07) | (0 if lid_open else 0x08)
    packet = bytes([
        PACKET_TYPE, PACKET_LENGTH - 2, 0x01, model_id & 0xFF, model_id >> 8, status, pods,
        case_flags, lid, color, connection_state,
    ]) + bytes(encrypted[:16]).ljust(16, b"\0")
    assert len(packet) == PACKET_LENGTH
    return packet
