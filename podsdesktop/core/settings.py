"""Persistent settings (JSON) in the platform's user config directory."""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

log = logging.getLogger(__name__)


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "PodsDesktop"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PodsDesktop"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "podsdesktop"


def state_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "PodsDesktop"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "PodsDesktop"
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "podsdesktop"


@dataclass
class Settings:
    device_address: str | None = None   # classic Bluetooth address of the bound device
    device_name: str = ""
    model_id: int | None = None
    irk: str | None = None              # hex, as received over AAP (LSB first)
    enc_key: str | None = None          # hex
    rssi_min: int = -80
    ear_detection: bool = True          # pause/resume media when pods leave/enter the ears
    low_latency: bool = False           # keep the audio sink awake with silence
    popup_on_lid: bool = True
    popup_seconds: int = 10
    notifications: bool = True
    low_battery_threshold: int = 20
    language: str = "auto"              # auto | ro | en
    ble_scan: bool = True
    aap: bool = True                    # use the AAP session on Linux
    autostart: bool = False
    tray_show_percent: bool = True
    path: Path = field(default_factory=lambda: config_dir() / "settings.json", repr=False, compare=False)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        settings = cls()
        if path is not None:
            settings.path = path
        try:
            raw = json.loads(settings.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return settings
        except (OSError, ValueError) as exc:
            log.warning("settings unreadable (%s), using defaults", exc)
            return settings
        names = {f.name for f in fields(cls)} - {"path"}
        for key, value in raw.items():
            if key in names:
                setattr(settings, key, value)
        return settings

    def save(self) -> None:
        data = {k: v for k, v in asdict(self).items() if k != "path"}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            log.warning("could not save settings: %s", exc)

    # ---- keys ----------------------------------------------------------------------------
    @property
    def irk_bytes(self) -> bytes | None:
        return bytes.fromhex(self.irk) if self.irk else None

    @property
    def enc_key_bytes(self) -> bytes | None:
        return bytes.fromhex(self.enc_key) if self.enc_key else None

    @property
    def keys_known(self) -> bool:
        return bool(self.irk and self.enc_key)

    def set_keys(self, irk: bytes | None, enc_key: bytes | None) -> bool:
        changed = False
        if irk and len(irk) == 16 and irk.hex() != self.irk:
            self.irk, changed = irk.hex(), True
        if enc_key and len(enc_key) == 16 and enc_key.hex() != self.enc_key:
            self.enc_key, changed = enc_key.hex(), True
        return changed

    def bind(self, address: str | None, name: str = "", model_id: int | None = None) -> None:
        if address != self.device_address:
            # a different device: forget the keys of the old one
            self.irk = self.enc_key = None
        self.device_address = address
        self.device_name = name
        self.model_id = model_id
