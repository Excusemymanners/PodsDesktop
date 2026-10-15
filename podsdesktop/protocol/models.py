"""Apple and Beats Bluetooth product ids.

The same 16-bit id shows up in three places: the classic Bluetooth Device ID record
(``Modalias: bluetooth:v004Cp2014``), the proximity pairing advertisement (bytes 3–4,
little-endian) and the AAP metadata. Sources: AirPodsDesktop, LibrePods, The Apple Wiki.

Unknown ids inside Apple's audio range are still accepted and shown generically instead of
being dropped, so a brand-new model keeps working until it gets a proper name.
"""

from __future__ import annotations

from dataclasses import dataclass

APPLE_VENDOR_ID = 0x004C

EARBUDS = "earbuds"   # two pods + a case: three batteries
HEADSET = "headset"   # over-ear / neckband: one battery
SPEAKER = "speaker"   # one battery, never worn


@dataclass(frozen=True)
class ModelInfo:
    pid: int
    name: str
    kind: str = EARBUDS
    family: str = "airpods"  # icon family: airpods, airpods_pro, airpods_max, beats

    @property
    def is_known(self) -> bool:
        return self.pid in MODELS


def _m(pid: int, name: str, kind: str = EARBUDS, family: str = "airpods") -> ModelInfo:
    return ModelInfo(pid, name, kind, family)


MODELS: dict[int, ModelInfo] = {
    m.pid: m
    for m in (
        _m(0x2002, "AirPods (1st generation)"),
        _m(0x200F, "AirPods (2nd generation)"),
        _m(0x2013, "AirPods (3rd generation)"),
        _m(0x2019, "AirPods 4"),
        _m(0x201B, "AirPods 4 (ANC)"),
        _m(0x2030, "AirPods 5"),
        _m(0x2036, "AirPods 5"),
        _m(0x200E, "AirPods Pro", family="airpods_pro"),
        _m(0x2014, "AirPods Pro 2", family="airpods_pro"),
        _m(0x2024, "AirPods Pro 2 (USB-C)", family="airpods_pro"),
        _m(0x2027, "AirPods Pro 3", family="airpods_pro"),
        _m(0x202B, "AirPods Pro (unreleased)", family="airpods_pro"),
        _m(0x202C, "AirPods Pro (unreleased)", family="airpods_pro"),
        _m(0x200A, "AirPods Max", HEADSET, "airpods_max"),
        _m(0x201F, "AirPods Max (USB-C)", HEADSET, "airpods_max"),
        _m(0x202D, "AirPods Max 2", HEADSET, "airpods_max"),
        _m(0x2003, "Powerbeats 3", HEADSET, "beats"),
        _m(0x2005, "BeatsX", HEADSET, "beats"),
        _m(0x2006, "Beats Solo3 Wireless", HEADSET, "beats"),
        _m(0x2009, "Beats Studio3 Wireless", HEADSET, "beats"),
        _m(0x200B, "Powerbeats Pro", EARBUDS, "beats"),
        _m(0x200C, "Beats Solo Pro", HEADSET, "beats"),
        _m(0x200D, "Powerbeats (4th generation)", HEADSET, "beats"),
        _m(0x2010, "Beats Flex", HEADSET, "beats"),
        _m(0x2011, "Beats Studio Buds", EARBUDS, "beats"),
        _m(0x2012, "Beats Fit Pro", EARBUDS, "beats"),
        _m(0x2016, "Beats Studio Buds +", EARBUDS, "beats"),
        _m(0x2017, "Beats Studio Pro", HEADSET, "beats"),
        _m(0x201A, "Beats Pill", SPEAKER, "beats"),
        _m(0x2025, "Beats Solo 4", HEADSET, "beats"),
        _m(0x2026, "Beats Solo Buds", EARBUDS, "beats"),
        _m(0x2031, "Beats Solo Buds (unreleased)", EARBUDS, "beats"),
        _m(0x2038, "Beats 360", HEADSET, "beats"),
        _m(0x2600, "Beats Pill+", SPEAKER, "beats"),
    )
}

# Model numbers printed on the device, as reported in AAP metadata (opcode 0x1D).
MODEL_NUMBERS: dict[str, int] = {
    "A1523": 0x2002, "A1722": 0x2002,
    "A2031": 0x200F, "A2032": 0x200F,
    "A2564": 0x2013, "A2565": 0x2013,
    "A3050": 0x2019, "A3053": 0x2019, "A3054": 0x2019,
    "A3055": 0x201B, "A3056": 0x201B, "A3057": 0x201B,
    "A2083": 0x200E, "A2084": 0x200E,
    "A2698": 0x2014, "A2699": 0x2014, "A2931": 0x2014,
    "A3047": 0x2024, "A3048": 0x2024, "A3049": 0x2024,
    "A2096": 0x200A,
    "A3184": 0x201F,
}


def is_apple_audio_pid(pid: int) -> bool:
    return 0x2000 <= pid <= 0x2FFF


def lookup(pid: int) -> ModelInfo:
    """Model info for a product id; unknown ids get a generic but usable entry."""
    try:
        return MODELS[pid]
    except KeyError:
        return ModelInfo(pid, f"Apple audio device (0x{pid:04X})")


def lookup_model_number(model_number: str) -> ModelInfo | None:
    pid = MODEL_NUMBERS.get(model_number.strip().upper())
    return lookup(pid) if pid is not None else None
