"""The options form shared by the setup assistant and the settings dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QGroupBox, QSpinBox, QVBoxLayout, QWidget

from ..core.settings import Settings
from . import i18n

CHECKS = (
    ("behaviour", "ear_detection"), ("behaviour", "popup_on_lid"), ("behaviour", "notifications"),
    ("behaviour", "low_latency"), ("general", "tray_show_percent"), ("general", "autostart"),
)


class OptionsWidget(QWidget):
    def __init__(self, settings: Settings, advanced: bool = False, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.checks: dict[str, QCheckBox] = {}
        layout = QVBoxLayout(self)
        groups: dict[str, QVBoxLayout] = {}
        for group_key in ("behaviour", "general"):
            box = QGroupBox(i18n.t(group_key))
            groups[group_key] = QVBoxLayout(box)
            layout.addWidget(box)
        for group_key, key in CHECKS:
            check = QCheckBox(i18n.t(key))
            groups[group_key].addWidget(check)
            self.checks[key] = check
        self.language = QComboBox()
        self.language.addItem(i18n.t("lang_auto"), "auto")
        self.language.addItem("Română", "ro")
        self.language.addItem("English", "en")
        form = QFormLayout()
        form.addRow(i18n.t("language"), self.language)
        self.rssi = self.popup_seconds = None
        if advanced:
            self.rssi = QSpinBox()
            self.rssi.setRange(-100, -30)
            self.rssi.setSuffix(" dBm")
            self.popup_seconds = QSpinBox()
            self.popup_seconds.setRange(3, 60)
            form.addRow(i18n.t("rssi_min"), self.rssi)
            form.addRow(i18n.t("popup_seconds"), self.popup_seconds)
        groups["general"].addLayout(form)
        self.load()

    def load(self) -> None:
        for key, check in self.checks.items():
            check.setChecked(bool(getattr(self.settings, key)))
        index = self.language.findData(self.settings.language if self.settings.language in ("ro", "en") else "auto")
        self.language.setCurrentIndex(max(0, index))
        if self.rssi is not None:
            self.rssi.setValue(int(self.settings.rssi_min))
            self.popup_seconds.setValue(int(self.settings.popup_seconds))

    def apply(self) -> None:
        for key, check in self.checks.items():
            setattr(self.settings, key, check.isChecked())
        self.settings.language = self.language.currentData()
        if self.rssi is not None:
            self.settings.rssi_min = self.rssi.value()
            self.settings.popup_seconds = self.popup_seconds.value()
