"""Settings window: device, options, advanced values, device keys (copy on Linux, paste on Windows)."""

from __future__ import annotations

import re

from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QVBoxLayout)

from ..core.bluetooth import PairedDevice
from ..core.settings import Settings
from . import i18n, images
from .options import OptionsWidget

HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, devices: list[PairedDevice], parent=None):
        super().__init__(parent)
        self.settings = settings
        self.keys_changed = False
        self.setObjectName("podsSettings")
        self.setWindowTitle(i18n.t("settings_dialog").rstrip("…"))
        self.setWindowIcon(images.app_icon())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)

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

        keys_box = QGroupBox(i18n.t("keys"))
        keys_layout = QVBoxLayout(keys_box)
        hint = QLabel(i18n.t("keys_text"))
        hint.setObjectName("pageText")
        hint.setWordWrap(True)
        keys_layout.addWidget(hint)
        keys_form = QFormLayout()
        self.irk = QLineEdit(settings.irk or "")
        self.enc = QLineEdit(settings.enc_key or "")
        for edit in (self.irk, self.enc):
            edit.setPlaceholderText("32 hex")
            edit.setMaxLength(32)
            edit.textChanged.connect(self._keys_edited)
        keys_form.addRow(i18n.t("irk"), self.irk)
        keys_form.addRow(i18n.t("enc_key"), self.enc)
        keys_layout.addLayout(keys_form)
        row = QHBoxLayout()
        self.keys_status = QLabel("")
        self.keys_status.setObjectName("pageText")
        self.copy_button = QPushButton(i18n.t("keys_copy"))
        self.copy_button.clicked.connect(self._copy_keys)
        self.paste_button = QPushButton(i18n.t("keys_paste"))
        self.paste_button.clicked.connect(self._paste_keys)
        row.addWidget(self.keys_status, 1)
        row.addWidget(self.copy_button)
        row.addWidget(self.paste_button)
        keys_layout.addLayout(row)
        layout.addWidget(keys_box)
        self._keys_edited()

        self.run_setup = QPushButton(i18n.t("run_setup"))
        layout.addWidget(self.run_setup)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setMinimumWidth(520)

    # ---- keys --------------------------------------------------------------------------
    def _keys_valid(self) -> bool:
        return bool(HEX32.match(self.irk.text().strip()) and HEX32.match(self.enc.text().strip()))

    def _keys_edited(self) -> None:
        if self._keys_valid():
            self.keys_status.setText(i18n.t("keys_known"))
        elif self.irk.text().strip() or self.enc.text().strip():
            self.keys_status.setText(i18n.t("keys_invalid"))
        else:
            self.keys_status.setText(i18n.t("keys_unknown"))
        self.copy_button.setEnabled(self._keys_valid())

    def _copy_keys(self) -> None:
        QApplication.clipboard().setText(f"{self.irk.text().strip().lower()}:{self.enc.text().strip().lower()}")
        self.keys_status.setText(i18n.t("keys_copied"))

    def _paste_keys(self) -> None:
        text = QApplication.clipboard().text().strip()
        parts = [p for p in re.split(r"[\s:,;]+", text) if p]
        if len(parts) == 2 and all(HEX32.match(p) for p in parts):
            self.irk.setText(parts[0].lower())
            self.enc.setText(parts[1].lower())
        else:
            self.keys_status.setText(i18n.t("keys_invalid"))

    def selected_address(self) -> str | None:
        return self.device.currentData()

    def apply(self) -> None:
        self.options.apply()
        irk, enc = self.irk.text().strip().lower(), self.enc.text().strip().lower()
        if self._keys_valid() and (irk != (self.settings.irk or "") or enc != (self.settings.enc_key or "")):
            self.settings.irk, self.settings.enc_key = irk, enc
            self.keys_changed = True
        elif not irk and not enc and (self.settings.irk or self.settings.enc_key):
            self.settings.irk = self.settings.enc_key = None
            self.keys_changed = True
