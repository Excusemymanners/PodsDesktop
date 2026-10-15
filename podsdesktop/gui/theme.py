"""Colours and the scoped stylesheet for the app's own windows (the tray menu stays native)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette


@dataclass(frozen=True)
class Palette:
    dark: bool
    bg: str
    card: str
    card_hover: str
    text: str
    dim: str
    accent: str
    green: str
    yellow: str
    red: str
    border: str


DARK = Palette(True, "#1c1c1e", "#2c2c2e", "#3a3a3c", "#f2f2f7", "#98989d", "#0a84ff", "#30d158", "#ffd60a", "#ff453a", "rgba(255,255,255,0.10)")
LIGHT = Palette(False, "#f2f2f7", "#ffffff", "#f0f0f5", "#1c1c1e", "#6e6e73", "#007aff", "#34c759", "#ffcc00", "#ff3b30", "rgba(0,0,0,0.08)")


def is_dark() -> bool:
    forced = os.environ.get("PODSDESKTOP_THEME", "").lower()
    if forced in ("dark", "light"):
        return forced == "dark"
    hints = QGuiApplication.styleHints()
    scheme = getattr(hints, "colorScheme", None)
    if scheme is not None:
        try:
            value = scheme()
            if value == Qt.ColorScheme.Dark:
                return True
            if value == Qt.ColorScheme.Light:
                return False
        except Exception:  # noqa: BLE001
            pass
    return QGuiApplication.palette().color(QPalette.Window).lightness() < 128


def palette() -> Palette:
    return DARK if is_dark() else LIGHT


def level_color(pal: Palette, level: int | None) -> QColor:
    if level is None:
        return QColor(pal.dim)
    if level <= 20:
        return QColor(pal.red)
    if level <= 40:
        return QColor(pal.yellow)
    return QColor(pal.green)


def stylesheet(pal: Palette) -> str:
    from .images import asset_path

    check = asset_path("check.svg").as_posix()
    scopes = "#podsWizard, #podsSettings"
    inner = lambda sel: ", ".join(f"{scope} {sel}" for scope in ("#podsWizard", "#podsSettings"))  # noqa: E731
    return f"""
{scopes} {{ background: {pal.bg}; }}
{inner("QWizardPage")} {{ background: {pal.bg}; }}
{inner("QWidget")} {{ color: {pal.text}; font-size: 13px; }}
{inner("QLineEdit")} {{ background: {pal.card}; color: {pal.text}; border: 1px solid {pal.border}; border-radius: 8px; padding: 5px 10px; selection-background-color: {pal.accent}; }}
{inner("QLineEdit:focus")} {{ border-color: {pal.accent}; }}
{inner("QLabel#pageTitle")} {{ font-size: 22px; font-weight: 700; padding-bottom: 2px; }}
{inner("QLabel#pageStep")} {{ color: {pal.dim}; font-size: 12px; }}
{inner("QLabel#pageText")} {{ color: {pal.dim}; font-size: 13px; line-height: 150%; }}
{inner("QLabel#statusOk")} {{ color: white; background: {pal.green}; border-radius: 12px; padding: 5px 14px; font-weight: 600; }}
{inner("QLabel#statusBad")} {{ color: white; background: {pal.red}; border-radius: 12px; padding: 5px 14px; font-weight: 600; }}
{inner("QLabel#statusWait")} {{ color: {pal.text}; background: {pal.card}; border-radius: 12px; padding: 5px 14px; }}
{inner("QLabel#liveStatus")} {{ font-size: 15px; font-weight: 600; }}
{inner("QPushButton")} {{ background: {pal.card}; color: {pal.text}; border: 1px solid {pal.border}; border-radius: 9px; padding: 7px 18px; min-height: 18px; }}
{inner("QPushButton:hover")} {{ background: {pal.card_hover}; border-color: {pal.accent}; }}
{inner("QPushButton:default")} {{ background: {pal.accent}; color: white; border-color: {pal.accent}; }}
{inner("QPushButton:default:hover")} {{ background: {pal.accent}; }}
{inner("QPushButton:disabled")} {{ color: {pal.dim}; }}
{inner("QListWidget")} {{ background: {pal.card}; border: 1px solid {pal.border}; border-radius: 14px; padding: 6px; outline: 0; font-size: 14px; }}
{inner("QListWidget::item")} {{ padding: 10px; border-radius: 10px; margin: 2px; }}
{inner("QListWidget::item:hover")} {{ background: {pal.card_hover}; }}
{inner("QListWidget::item:selected")} {{ background: {pal.accent}; color: white; }}
{inner("QCheckBox")} {{ spacing: 10px; padding: 4px 0; }}
{inner("QCheckBox::indicator")} {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {pal.border}; background: {pal.card}; }}
{inner("QCheckBox::indicator:checked")} {{ background: {pal.accent}; border-color: {pal.accent}; image: url("{check}"); }}
{inner("QComboBox, QSpinBox")} {{ background: {pal.card}; color: {pal.text}; border: 1px solid {pal.border}; border-radius: 8px; padding: 5px 10px; min-height: 20px; }}
{inner("QSpinBox::up-button, QSpinBox::down-button")} {{ width: 18px; border: 0; background: transparent; }}
{inner("QComboBox::drop-down")} {{ border: 0; width: 24px; }}
{inner("QComboBox QAbstractItemView")} {{ background: {pal.card}; color: {pal.text}; selection-background-color: {pal.accent}; selection-color: white; border: 1px solid {pal.border}; }}
{inner("QGroupBox")} {{ border: 1px solid {pal.border}; border-radius: 12px; margin-top: 14px; padding: 14px 10px 8px 10px; background: {pal.card}; }}
{inner("QGroupBox::title")} {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; color: {pal.dim}; font-weight: 600; }}
{inner("QDialogButtonBox QPushButton")} {{ min-width: 90px; }}
"""
