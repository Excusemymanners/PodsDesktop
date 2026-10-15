"""The one state object the UI, CLI and notifications read."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from ..protocol.models import EARBUDS, HEADSET, ModelInfo, lookup

SOURCE_NONE = "none"
SOURCE_BLE = "ble"            # advertisement, 10 % steps
SOURCE_BLE_EXACT = "ble-exact"  # advertisement decrypted with the device key, 1 %
SOURCE_AAP = "aap"            # live AAP session, 1 %


@dataclass
class Component:
    level: int | None = None
    charging: bool = False
    in_ear: bool = False
    available: bool = False
    exact: bool = False

    @classmethod
    def unavailable(cls) -> "Component":
        return cls()

    def text(self, unknown: str = "–") -> str:
        if not self.available or self.level is None:
            return unknown
        return f"{self.level}%" + (" ⚡" if self.charging else "")


@dataclass
class DeviceState:
    address: str | None = None
    name: str = ""
    model_id: int | None = None
    model_number: str = ""
    firmware: str = ""
    left: Component = field(default_factory=Component)
    right: Component = field(default_factory=Component)
    case: Component = field(default_factory=Component)
    lid_open: bool | None = None
    both_in_case: bool = False
    connected: bool = False       # classic Bluetooth link (audio) is up
    aap_connected: bool = False   # we hold an AAP session (Linux only)
    scanning: bool = False
    noise_mode: int | None = None
    allowed_modes: list[int] = field(default_factory=lambda: [1, 2, 3, 4])
    conversational_awareness: bool | None = None
    controls: dict[int, list[int]] = field(default_factory=dict)
    source: str = SOURCE_NONE
    rssi: int | None = None
    updated: float = 0.0

    # ---- helpers ---------------------------------------------------------------------
    @property
    def model(self) -> ModelInfo | None:
        return lookup(self.model_id) if self.model_id is not None else None

    @property
    def kind(self) -> str:
        return self.model.kind if self.model else EARBUDS

    @property
    def is_headset(self) -> bool:
        return self.kind == HEADSET

    @property
    def display_name(self) -> str:
        name = (self.name or "").replace(" - Find My", "").strip()
        if name and self.model and name.lower() in ("airpods", "airpods max", "airpods pro"):
            return self.model.name
        return name or (self.model.name if self.model else "AirPods")

    @property
    def has_battery(self) -> bool:
        return any(c.available for c in (self.left, self.right, self.case))

    @property
    def both_in_ear(self) -> bool:
        if self.is_headset:
            return self.left.in_ear
        return self.left.in_ear and self.right.in_ear

    @property
    def any_in_ear(self) -> bool:
        return self.left.in_ear or self.right.in_ear

    def min_pod_level(self) -> int | None:
        levels = [c.level for c in (self.left, self.right) if c.available and c.level is not None]
        return min(levels) if levels else None

    def levels_text(self) -> str:
        if self.is_headset:
            return self.left.text()
        return f"L {self.left.text()}  R {self.right.text()}  C {self.case.text()}"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["model_name"] = self.model.name if self.model else None
        data["display_name"] = self.display_name
        data["kind"] = self.kind
        return data

    def touch(self) -> None:
        self.updated = time.time()
