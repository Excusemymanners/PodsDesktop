"""Product images per model, loaded from the bundled assets (works from a wheel and from PyInstaller)."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

from ..protocol.models import lookup

IMAGES: dict[int, str] = {
    0x2002: "AirPods_1.png", 0x200F: "AirPods_2.png", 0x2013: "AirPods_3.png",
    0x2019: "AirPods_4.png", 0x201B: "AirPods_4_ANC.png", 0x2030: "AirPods_4.png", 0x2036: "AirPods_4.png",
    0x200E: "AirPods_Pro.png", 0x2014: "AirPods_Pro_2.png", 0x2024: "AirPods_Pro_2.png",
    0x2027: "AirPods_Pro_3.png", 0x202B: "AirPods_Pro_3.png", 0x202C: "AirPods_Pro_3.png",
    0x200A: "AirPods_Max.png", 0x201F: "AirPods_Max.png", 0x202D: "AirPods_Max.png",
    0x2012: "Beats_Fit_Pro.png",
}
FAMILY_DEFAULT = {"airpods": "AirPods_3.png", "airpods_pro": "AirPods_Pro_2.png",
                  "airpods_max": "AirPods_Max.png", "beats": "Beats_Fit_Pro.png"}

_cache: dict[tuple[str, int], QPixmap] = {}


def asset_path(name: str) -> Path:
    return Path(str(files("podsdesktop.gui.assets").joinpath(name)))


def image_name(model_id: int | None) -> str:
    if model_id is None:
        return FAMILY_DEFAULT["airpods"]
    if model_id in IMAGES:
        return IMAGES[model_id]
    return FAMILY_DEFAULT.get(lookup(model_id).family, FAMILY_DEFAULT["airpods"])


def model_pixmap(model_id: int | None, height: int | None = None) -> QPixmap:
    name = image_name(model_id)
    key = (name, height or 0)
    pix = _cache.get(key)
    if pix is None:
        pix = QPixmap(str(asset_path(name)))
        if height and not pix.isNull():
            pix = pix.scaledToHeight(height, Qt.SmoothTransformation)
        _cache[key] = pix
    return pix


def model_icon(model_id: int | None) -> QIcon:
    return QIcon(model_pixmap(model_id, 64))


def app_icon() -> QIcon:
    path = asset_path("icon.png")
    return QIcon(str(path)) if path.exists() else QIcon()
