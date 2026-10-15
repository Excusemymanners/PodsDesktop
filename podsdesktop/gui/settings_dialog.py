"""Settings window: options, device, advanced values."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QPushButton, QVBoxLayout

from ..core.bluetooth import PairedDevice
from ..core.settings import Settings
from . import i18n, images
from .options import OptionsWidget


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, devices: list[PairedDevice], parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(i18n.t("settings_dialog"))
        self.setWindowIcon(images.app_icon())
        layout = QVBoxLayout(self)
        box = QGroupBox(i18n.t("device"))
        form = QFormLayout(box)
        self.device = QComboBox()
        self.device.addItem(i18n.t("no_device"), None)
        for d in devices:
            self.device.addItem(images.model_icon(d.product_id), f"{d.name} ({d.model_name or d.address})", d.address)
        index = self.device.findData(settings.device_address)
        self.device.setCurrentIndex(max(0, index))
        form.addRow(i18n.t("device"), self.device)
        layout.addWidget(box)
        self.options = OptionsWidget(settings, advanced=True)
        layout.addWidget(self.options)
        self.run_setup = QPushButton(i18n.t("run_setup"))
        layout.addWidget(self.run_setup)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setMinimumWidth(460)

    def selected_address(self) -> str | None:
        return self.device.currentData()

    def apply(self) -> None:
        self.options.apply()
