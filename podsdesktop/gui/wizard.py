"""First-run setup assistant (also reachable from the tray menu)."""

from __future__ import annotations

import sys

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout, QWizard, QWizardPage)

from ..core.bluetooth import PairedDevice
from ..core.settings import Settings
from ..core.state import DeviceState
from ..core.system import open_bluetooth_settings
from . import i18n, images
from .options import OptionsWidget


class _Page(QWizardPage):
    def __init__(self, wizard: "SetupWizard", title_key: str, text_key: str):
        super().__init__()
        self.wiz = wizard
        self.setTitle(i18n.t(title_key))
        self.body = QVBoxLayout(self)
        intro = QLabel(i18n.t(text_key))
        intro.setWordWrap(True)
        self.body.addWidget(intro)


class WelcomePage(_Page):
    def __init__(self, wizard):
        super().__init__(wizard, "welcome_title", "welcome_text")
        pic = QLabel()
        pic.setPixmap(images.model_pixmap(wizard.settings.model_id, 120))
        pic.setAlignment(Qt.AlignCenter)
        self.body.addWidget(pic)
        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.t("language")))
        self.options = OptionsWidget(wizard.settings)
        self.options.hide()
        self.language = self.options.language
        self.language.setParent(self)
        row.addWidget(self.language)
        row.addStretch(1)
        self.body.addLayout(row)
        self.language.currentIndexChanged.connect(self._language_changed)

    def _language_changed(self) -> None:
        code = self.language.currentData()
        if code != self.wiz.settings.language:
            self.wiz.settings.language = code
            self.wiz.language_changed.emit(code)


class BluetoothPage(_Page):
    def __init__(self, wizard):
        super().__init__(wizard, "bt_title", "bt_text")
        self.status = QLabel(i18n.t("bt_unknown"))
        self.status.setStyleSheet("font-weight: 600;")
        self.body.addWidget(self.status)
        row = QHBoxLayout()
        self.turn_on = QPushButton(i18n.t("bt_turn_on"))
        self.turn_on.clicked.connect(lambda: self.wiz.request("power_on"))
        self.open_settings = QPushButton(i18n.t("bt_open_settings"))
        self.open_settings.clicked.connect(open_bluetooth_settings)
        row.addWidget(self.turn_on)
        row.addWidget(self.open_settings)
        row.addStretch(1)
        self.body.addLayout(row)
        self.body.addStretch(1)
        self.powered: bool | None = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.wiz.request("adapter"))

    def initializePage(self) -> None:  # noqa: N802
        self.wiz.request("adapter")
        self.timer.start(2000)

    def cleanupPage(self) -> None:  # noqa: N802
        self.timer.stop()

    def set_powered(self, powered: bool) -> None:
        self.powered = powered
        self.status.setText(i18n.t("bt_on" if powered else "bt_off"))
        self.status.setStyleSheet("font-weight: 600; color: %s;" % ("#34c759" if powered else "#ff3b30"))
        self.turn_on.setVisible(not powered)
        self.completeChanged.emit()

    def isComplete(self) -> bool:  # noqa: N802
        return bool(self.powered)

    def validatePage(self) -> bool:  # noqa: N802
        self.timer.stop()
        return True


class DevicePage(_Page):
    def __init__(self, wizard):
        super().__init__(wizard, "device_title", "device_text")
        self.list = QListWidget()
        self.list.setIconSize(QSize(72, 36))
        self.list.itemSelectionChanged.connect(self.completeChanged.emit)
        self.body.addWidget(self.list, 1)
        self.empty = QLabel(i18n.t("device_none"))
        self.empty.setStyleSheet("color: #8e8e93;")
        self.body.addWidget(self.empty)
        row = QHBoxLayout()
        refresh = QPushButton(i18n.t("refresh"))
        refresh.clicked.connect(lambda: self.wiz.request("devices"))
        open_settings = QPushButton(i18n.t("bt_open_settings"))
        open_settings.clicked.connect(open_bluetooth_settings)
        row.addWidget(refresh)
        row.addWidget(open_settings)
        row.addStretch(1)
        self.body.addLayout(row)
        self.later = QCheckBox(i18n.t("device_later"))
        self.later.toggled.connect(self.completeChanged.emit)
        self.body.addWidget(self.later)
        self.devices: list[PairedDevice] = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.wiz.request("devices"))

    def initializePage(self) -> None:  # noqa: N802
        self.wiz.request("devices")
        self.timer.start(3000)

    def cleanupPage(self) -> None:  # noqa: N802
        self.timer.stop()

    def set_devices(self, devices: list[PairedDevice]) -> None:
        selected = self.selected_address() or self.wiz.settings.device_address
        self.devices = devices
        self.list.clear()
        for d in devices:
            item = QListWidgetItem(images.model_icon(d.product_id), f"{d.name}\n{d.model_name or d.address}")
            item.setData(Qt.UserRole, d.address)
            self.list.addItem(item)
            if selected and d.address.upper() == selected.upper():
                item.setSelected(True)
        if devices and not self.list.selectedItems():
            self.list.item(0).setSelected(True)
        self.empty.setVisible(not devices)
        self.completeChanged.emit()

    def selected_address(self) -> str | None:
        items = self.list.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    def isComplete(self) -> bool:  # noqa: N802
        return bool(self.selected_address()) or self.later.isChecked()

    def validatePage(self) -> bool:  # noqa: N802
        self.timer.stop()
        address = self.selected_address()
        if address and address.upper() != (self.wiz.settings.device_address or "").upper():
            self.wiz.request("bind", address)
        return True


class OptionsPage(_Page):
    def __init__(self, wizard):
        super().__init__(wizard, "options_title", "options_text")
        self.options = OptionsWidget(wizard.settings)
        self.options.language.hide()
        self.body.addWidget(self.options)

    def validatePage(self) -> bool:  # noqa: N802
        self.options.apply()
        return True


class DonePage(_Page):
    def __init__(self, wizard):
        super().__init__(wizard, "done_title", "done_text")
        if sys.platform.startswith("linux"):
            hint = QLabel(i18n.t("done_keys_hint"))
            hint.setWordWrap(True)
            self.body.addWidget(hint)
        self.pic = QLabel()
        self.pic.setAlignment(Qt.AlignCenter)
        self.body.addWidget(self.pic)
        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.body.addWidget(self.status)
        self.body.addStretch(1)

    def initializePage(self) -> None:  # noqa: N802
        self.set_state(self.wiz.state)

    def set_state(self, state: DeviceState | None) -> None:
        if state is None:
            return
        self.pic.setPixmap(images.model_pixmap(state.model_id, 110))
        text = state.display_name
        if state.has_battery:
            text += "\n" + state.levels_text()
        else:
            text += "\n" + (i18n.t("connected") if state.connected else i18n.t("not_connected"))
        self.status.setText(text)


class SetupWizard(QWizard):
    """Pages talk to the engine only through ``request``; the app answers through ``on_event``."""

    requested = Signal(str, object)     # ("adapter"|"power_on"|"devices"|"bind", payload)
    language_changed = Signal(str)
    finished_setup = Signal()

    def __init__(self, settings: Settings, state: DeviceState | None):
        super().__init__()
        self.settings = settings
        self.state = state
        self.setWindowTitle(i18n.t("wizard_title"))
        self.setWindowIcon(images.app_icon())
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setMinimumSize(560, 480)
        self.page_welcome = WelcomePage(self)
        self.page_bluetooth = BluetoothPage(self)
        self.page_device = DevicePage(self)
        self.page_options = OptionsPage(self)
        self.page_done = DonePage(self)
        for page in (self.page_welcome, self.page_bluetooth, self.page_device, self.page_options, self.page_done):
            self.addPage(page)
        self.accepted.connect(self._finished)

    def request(self, what: str, payload=None) -> None:
        self.requested.emit(what, payload)

    def on_event(self, name: str, payload) -> None:
        if name == "adapter":
            self.page_bluetooth.set_powered(bool(payload))
        elif name == "devices":
            self.page_device.set_devices(list(payload))
        elif name == "state":
            self.state = payload
            self.page_done.set_state(payload)

    def _finished(self) -> None:
        self.settings.setup_done = True
        self.settings.save()
        self.finished_setup.emit()
