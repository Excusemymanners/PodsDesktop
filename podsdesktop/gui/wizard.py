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

TOTAL_STEPS = 5


class _Page(QWizardPage):
    """A page with its own header (title + step counter + intro), so the look is ours."""

    def __init__(self, wizard: "SetupWizard", step: int, title_key: str, text_key: str):
        super().__init__()
        self.wiz = wizard
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(28, 24, 28, 16)
        self.body.setSpacing(12)
        step_label = QLabel(i18n.t("step", n=step, total=TOTAL_STEPS))
        step_label.setObjectName("pageStep")
        title = QLabel(i18n.t(title_key))
        title.setObjectName("pageTitle")
        intro = QLabel(i18n.t(text_key))
        intro.setObjectName("pageText")
        intro.setWordWrap(True)
        self.body.addWidget(step_label)
        self.body.addWidget(title)
        self.body.addWidget(intro)
        self.body.addSpacing(6)


class WelcomePage(_Page):
    def __init__(self, wizard):
        super().__init__(wizard, 1, "welcome_title", "welcome_text")
        pic = QLabel()
        pic.setPixmap(images.model_pixmap(wizard.settings.model_id, 150))
        pic.setAlignment(Qt.AlignCenter)
        self.body.addStretch(1)
        self.body.addWidget(pic)
        self.body.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.t("language")))
        self.options = OptionsWidget(wizard.settings)
        self.options.hide()
        self.language = self.options.language
        self.language.setParent(self)
        self.language.setMinimumWidth(180)
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
        super().__init__(wizard, 2, "bt_title", "bt_text")
        self.status = QLabel(i18n.t("bt_unknown"))
        self.status.setObjectName("statusWait")
        row = QHBoxLayout()
        row.addWidget(self.status)
        row.addStretch(1)
        self.body.addLayout(row)
        buttons = QHBoxLayout()
        self.turn_on = QPushButton(i18n.t("bt_turn_on"))
        self.turn_on.clicked.connect(lambda: self.wiz.request("power_on"))
        self.open_settings = QPushButton(i18n.t("bt_open_settings"))
        self.open_settings.clicked.connect(open_bluetooth_settings)
        buttons.addWidget(self.turn_on)
        buttons.addWidget(self.open_settings)
        buttons.addStretch(1)
        self.body.addLayout(buttons)
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
        self.status.setObjectName("statusOk" if powered else "statusBad")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.turn_on.setVisible(not powered)
        self.completeChanged.emit()

    def isComplete(self) -> bool:  # noqa: N802
        return bool(self.powered)

    def validatePage(self) -> bool:  # noqa: N802
        self.timer.stop()
        return True


class DevicePage(_Page):
    def __init__(self, wizard):
        super().__init__(wizard, 3, "device_title", "device_text")
        self.list = QListWidget()
        self.list.setIconSize(QSize(96, 48))
        self.list.setSpacing(2)
        self.list.itemSelectionChanged.connect(self.completeChanged.emit)
        self.body.addWidget(self.list, 1)
        self.empty = QLabel(i18n.t("device_none"))
        self.empty.setObjectName("pageText")
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
        super().__init__(wizard, 4, "options_title", "options_text")
        self.options = OptionsWidget(wizard.settings)
        self.options.language.hide()
        self.body.addWidget(self.options)
        self.body.addStretch(1)

    def validatePage(self) -> bool:  # noqa: N802
        self.options.apply()
        return True


class DonePage(_Page):
    def __init__(self, wizard):
        super().__init__(wizard, 5, "done_title", "done_text")
        if sys.platform.startswith("linux"):
            hint = QLabel(i18n.t("done_keys_hint"))
            hint.setObjectName("pageText")
            hint.setWordWrap(True)
            self.body.addWidget(hint)
        self.body.addStretch(1)
        self.pic = QLabel()
        self.pic.setAlignment(Qt.AlignCenter)
        self.body.addWidget(self.pic)
        self.status = QLabel("")
        self.status.setObjectName("liveStatus")
        self.status.setAlignment(Qt.AlignCenter)
        self.body.addWidget(self.status)
        self.body.addStretch(1)

    def initializePage(self) -> None:  # noqa: N802
        self.set_state(self.wiz.state)

    def set_state(self, state: DeviceState | None) -> None:
        if state is None:
            return
        self.pic.setPixmap(images.model_pixmap(state.model_id, 120))
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
        self.setObjectName("podsWizard")
        self.setWindowTitle(i18n.t("wizard_title"))
        self.setWindowIcon(images.app_icon())
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.NoCancelButtonOnLastPage, True)
        self.setButtonText(QWizard.NextButton, i18n.t("next") + "  ›")
        self.setButtonText(QWizard.BackButton, "‹  " + i18n.t("back"))
        self.setButtonText(QWizard.FinishButton, i18n.t("finish"))
        self.setButtonText(QWizard.CancelButton, i18n.t("cancel"))
        self.setMinimumSize(600, 540)
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
