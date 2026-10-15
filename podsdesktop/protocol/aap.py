"""Apple Accessory Protocol (AAP / AACP) packets, as spoken over L2CAP PSM 0x1001.

Session setup (host -> accessory)::

    00 00 04 00 01 00 02 00 00 00 00 00 00 00 00 00   handshake
    04 00 04 00 4D 00 FF 00 00 00 00 00 00 00         host capabilities ("specific features")
    04 00 04 00 0F 00 FF FF FF FF FF                  subscribe to notifications

Every other packet is ``04 00 04 00 <opcode LE16> <payload>``. This module only builds and
parses bytes; the socket lives in :mod:`podsdesktop.core.aap_client`.
Sources: LibrePods docs, zeffd/airpods, own captures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PSM = 0x1001
SERVICE_UUID = "74ec2172-0bad-4d01-8f77-997b2be0722a"

HEADER = bytes.fromhex("04000400")
HANDSHAKE = bytes.fromhex("00000400010002000000000000000000")
HANDSHAKE_ACK = bytes.fromhex("01000400")
SET_SPECIFIC_FEATURES = bytes.fromhex("040004004d00ff00000000000000")
REQUEST_NOTIFICATIONS = bytes.fromhex("040004000f00ffffffffff")
REQUEST_PROXIMITY_KEYS = bytes.fromhex("0400040030000500")

OP_BATTERY = 0x0004
OP_EAR = 0x0006
OP_CONTROL = 0x0009
OP_NOTIFICATIONS = 0x000F
OP_DEVICE_INFO = 0x001D
OP_RENAME = 0x001E
OP_PAIRED_DEVICES = 0x002B
OP_KEYS_REQUEST = 0x0030
OP_KEYS_RESPONSE = 0x0031
OP_CONVERSATION_LEVEL = 0x004B
OP_HOST_CAPABILITIES = 0x004D

# Battery components and statuses (opcode 0x0004)
COMP_HEADSET = 0x01
COMP_RIGHT = 0x02
COMP_LEFT = 0x04
COMP_CASE = 0x08
COMPONENT_NAMES = {COMP_HEADSET: "headset", COMP_RIGHT: "right", COMP_LEFT: "left", COMP_CASE: "case"}

BATT_UNKNOWN = 0x00
BATT_CHARGING = 0x01
BATT_DISCHARGING = 0x02
BATT_DISCONNECTED = 0x04

# Ear detection (opcode 0x0006)
EAR_IN = 0x00
EAR_OUT = 0x01
EAR_IN_CASE = 0x02

# Control command identifiers (opcode 0x0009)
CTL_MIC_MODE = 0x01
CTL_EAR_DETECTION = 0x0A
CTL_LISTENING_MODE = 0x0D
CTL_SIRI_VOICE_TRIGGER = 0x12
CTL_CLICK_HOLD_MODE = 0x16
CTL_LISTENING_MODE_CONFIGS = 0x1A
CTL_ONE_BUD_ANC = 0x1B
CTL_CHIME_VOLUME = 0x1F
CTL_CONNECT_AUTOMATICALLY = 0x20
CTL_VOLUME_SWIPE = 0x25
CTL_ADAPTIVE_VOLUME = 0x26
CTL_CONVERSATIONAL_AWARENESS = 0x28
CTL_HEARING_AID = 0x2C
CTL_ADAPTIVE_ANC_STRENGTH = 0x2E
CTL_IN_CASE_TONE = 0x31
CTL_HEARING_ASSIST = 0x33
CTL_ALLOW_OFF_MODE = 0x34
CTL_SLEEP_DETECTION = 0x35
CTL_IN_CASE_TONE_VOLUME = 0x40

CONTROL_NAMES = {
    CTL_MIC_MODE: "Microphone", CTL_EAR_DETECTION: "Ear detection",
    CTL_LISTENING_MODE: "Listening mode", CTL_SIRI_VOICE_TRIGGER: "Siri voice trigger",
    CTL_CLICK_HOLD_MODE: "Press-and-hold action", CTL_LISTENING_MODE_CONFIGS: "Allowed modes",
    CTL_ONE_BUD_ANC: "One-bud ANC", CTL_CHIME_VOLUME: "Chime volume",
    CTL_CONNECT_AUTOMATICALLY: "Connect automatically", CTL_VOLUME_SWIPE: "Volume swipe",
    CTL_ADAPTIVE_VOLUME: "Adaptive volume", CTL_CONVERSATIONAL_AWARENESS: "Conversational awareness",
    CTL_HEARING_AID: "Hearing aid", CTL_ADAPTIVE_ANC_STRENGTH: "Adaptive ANC strength",
    CTL_IN_CASE_TONE: "In-case tone", CTL_HEARING_ASSIST: "Hearing assist",
    CTL_ALLOW_OFF_MODE: "Allow 'Off' in mode cycle", CTL_SLEEP_DETECTION: "Sleep detection",
    CTL_IN_CASE_TONE_VOLUME: "In-case tone volume",
}

# Listening (noise control) modes, values of control 0x0D
MODE_OFF = 1
MODE_ANC = 2
MODE_TRANSPARENCY = 3
MODE_ADAPTIVE = 4
MODE_NAMES = {MODE_OFF: "Off", MODE_ANC: "Noise Cancellation", MODE_TRANSPARENCY: "Transparency", MODE_ADAPTIVE: "Adaptive"}
MODE_KEYS = {"off": MODE_OFF, "anc": MODE_ANC, "transparency": MODE_TRANSPARENCY, "adaptive": MODE_ADAPTIVE}

TOGGLE_ON = 0x01
TOGGLE_OFF = 0x02


# ---------------------------------------------------------------------------- builders ---

def packet(opcode: int, payload: bytes = b"") -> bytes:
    return HEADER + opcode.to_bytes(2, "little") + payload


def control(identifier: int, *values: int) -> bytes:
    """Control command: identifier plus up to four data bytes, zero padded."""
    if not 0 <= len(values) <= 4:
        raise ValueError("a control command carries at most 4 data bytes")
    data = bytes(values) + bytes(4 - len(values))
    return packet(OP_CONTROL, bytes([identifier]) + data)


def set_listening_mode(mode: int) -> bytes:
    if mode not in MODE_NAMES:
        raise ValueError(f"unknown listening mode {mode}")
    return control(CTL_LISTENING_MODE, mode)


def set_toggle(identifier: int, enabled: bool) -> bytes:
    return control(identifier, TOGGLE_ON if enabled else TOGGLE_OFF)


def set_level(identifier: int, level: int) -> bytes:
    return control(identifier, max(0, min(100, int(level))))


def rename(name: str) -> bytes:
    raw = name.encode("utf-8")[:32]
    return packet(0x001A, bytes([0x01, len(raw), 0x00]) + raw)


# ----------------------------------------------------------------------------- events ----

@dataclass(frozen=True)
class BatteryComponent:
    component: int
    level: int
    status: int

    @property
    def name(self) -> str:
        return COMPONENT_NAMES.get(self.component, f"0x{self.component:02X}")

    @property
    def available(self) -> bool:
        return self.status != BATT_DISCONNECTED

    @property
    def charging(self) -> bool:
        return self.status == BATT_CHARGING


@dataclass(frozen=True)
class BatteryEvent:
    components: tuple[BatteryComponent, ...]

    def get(self, component: int) -> BatteryComponent | None:
        for c in self.components:
            if c.component == component:
                return c
        return None

    @property
    def primary_pod(self) -> int | None:
        """The first pod listed is the primary one (the one talking to us)."""
        for c in self.components:
            if c.component in (COMP_LEFT, COMP_RIGHT, COMP_HEADSET):
                return c.component
        return None


@dataclass(frozen=True)
class EarEvent:
    primary: int
    secondary: int

    @property
    def primary_in_ear(self) -> bool:
        return self.primary == EAR_IN

    @property
    def secondary_in_ear(self) -> bool:
        return self.secondary == EAR_IN

    @property
    def any_removed(self) -> bool:
        return self.primary != EAR_IN or self.secondary != EAR_IN


@dataclass(frozen=True)
class ControlEvent:
    identifier: int
    values: tuple[int, int, int, int]

    @property
    def value(self) -> int:
        return self.values[0]

    @property
    def name(self) -> str:
        return CONTROL_NAMES.get(self.identifier, f"Unknown 0x{self.identifier:02X}")


@dataclass(frozen=True)
class DeviceInfoEvent:
    name: str
    model_number: str
    manufacturer: str
    serial: str
    firmware: str
    strings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KeysEvent:
    irk: bytes | None
    enc_key: bytes | None


@dataclass(frozen=True)
class ConversationEvent:
    level: int  # 1/2 speaking (duck), 3 stopped, 8/9 normal


@dataclass(frozen=True)
class HandshakeAck:
    pass


@dataclass(frozen=True)
class UnknownEvent:
    opcode: int
    payload: bytes


Event = (
    BatteryEvent | EarEvent | ControlEvent | DeviceInfoEvent | KeysEvent | ConversationEvent
    | HandshakeAck | UnknownEvent
)


def _parse_battery(body: bytes) -> BatteryEvent | None:
    if not body:
        return None
    count = body[0]
    comps = []
    for i in range(count):
        off = 1 + i * 5
        if off + 5 > len(body):
            break
        comp, _spacer, level, status, _end = body[off : off + 5]
        comps.append(BatteryComponent(comp, min(level, 100), status))
    return BatteryEvent(tuple(comps)) if comps else None


def _parse_device_info(body: bytes) -> DeviceInfoEvent:
    # Five bytes of framing (00 02 d5 00 04) precede the NUL-separated strings.
    strings = []
    for chunk in body[5:].split(b"\x00"):
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if text and text.isprintable():
            strings.append(text)
    # Order: name, model number, manufacturer, serial, firmware, firmware, hw rev, updater, ...
    get = lambda i: strings[i] if i < len(strings) else ""  # noqa: E731
    name, model_number, manufacturer, serial, firmware = get(0), get(1), get(2), get(3), get(4)
    if not (len(model_number) == 5 and model_number[0] == "A" and model_number[1:].isdigit()):
        # Be tolerant about ordering: pick the first A-number and the first x.y.z version.
        model_number = next((s for s in strings if len(s) == 5 and s[0] == "A" and s[1:].isdigit()), model_number)
        firmware = next((s for s in strings if s.count(".") == 2 and s[0].isdigit()), firmware)
    return DeviceInfoEvent(name, model_number, manufacturer, serial, firmware, tuple(strings))


def _parse_keys(body: bytes) -> KeysEvent:
    # body: 00 <count> then TLVs: type(1) length(2, big-endian) reserved(1) value(length)
    irk = enc = None
    if len(body) >= 2:
        count = body[1]
        off = 2
        for _ in range(count):
            if off + 4 > len(body):
                break
            key_type = body[off]
            length = (body[off + 1] << 8) | body[off + 2]
            off += 4
            value = bytes(body[off : off + length])
            off += length
            if len(value) != length:
                break
            if key_type == 0x01:
                irk = value
            elif key_type == 0x04:
                enc = value
    return KeysEvent(irk, enc)


def parse(data: bytes) -> Event | None:
    """Parse one SDU received from the accessory."""
    if data.startswith(HANDSHAKE_ACK):
        return HandshakeAck()
    if len(data) < 6 or not data.startswith(HEADER):
        return None
    opcode = int.from_bytes(data[4:6], "little")
    body = bytes(data[6:])
    if opcode == OP_BATTERY:
        return _parse_battery(body)
    if opcode == OP_EAR:
        return EarEvent(body[0], body[1]) if len(body) >= 2 else None
    if opcode == OP_CONTROL:
        if len(body) >= 5:
            return ControlEvent(body[0], (body[1], body[2], body[3], body[4]))
        return None
    if opcode == OP_DEVICE_INFO:
        return _parse_device_info(body)
    if opcode == OP_KEYS_RESPONSE:
        return _parse_keys(body)
    if opcode == OP_CONVERSATION_LEVEL:
        # 02 00 01 <level>
        return ConversationEvent(body[3]) if len(body) >= 4 else None
    return UnknownEvent(opcode, body)


def allowed_modes_from_mask(mask: int) -> list[int]:
    """Control 0x1A bitmask -> list of listening mode values (0x01 Off ... 0x08 Adaptive)."""
    mask = mask or 0x0F
    return [mode for mode in (MODE_OFF, MODE_ANC, MODE_TRANSPARENCY, MODE_ADAPTIVE) if mask & (1 << (mode - 1))]
