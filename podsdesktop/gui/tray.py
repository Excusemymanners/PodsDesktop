"""System tray icon and menu."""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..core.bluetooth import PairedDevice
from ..core.settings import Settings
from ..core.state import DeviceState
from ..protocol import aap
from . import i18n, images
from .icons import tray_icon

MODE_KEYS = {aap.MODE_OFF: "mode_off", aap.MODE_ANC: "mode_anc", aap.MODE_TRANSPARENCY: "mode_transparency", aap.MODE_ADAPTIVE: "mode_adaptive"}
SETTING_KEYS = ("ear_detection", "low_latency", "popup_on_lid", "notifications", "ble_scan", "autostart")


class Tray(QObject):
    mode_selected = Signal(int)
    ca_toggled = Signal(bool)
    connect_clicked = Signal()
    disconnect_clicked = Signal()
    bind_selected = Signal(str)
    refresh_clicked = Signal()
    setting_toggled = Signal(str, bool)
    show_battery_clicked = Signal()
    setup_clicked = Signal()
    settings_clicked = Signal()
    fetch_keys_clicked = Signal()
    about_clicked = Signal()
    quit_clicked = Signal()

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.state: DeviceState | None = None
        self.icon = QSystemTrayIcon(tray_icon(None), self)
        self.menu = QMenu()
        self.menu.setWindowIcon(images.app_icon())
        self._build_menu()
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._activated)
        self.icon.setToolTip("PodsDesktop")

    # ---- menu ------------------------------------------------------------------------
    def _build_menu(self) -> None:
        m = self.menu
        self.a_title = m.addAction(i18n.t("no_device"))
        self.a_title.setEnabled(False)
        self.a_levels = m.addAction("")
        self.a_levels.setEnabled(False)
        m.addSeparator()

        self.noise_menu = m.addMenu(i18n.t("noise_control"))
        self.mode_group = QActionGroup(self)
        self.mode_actions: dict[int, QAction] = {}
        for mode, key in MODE_KEYS.items():
            action = self.noise_menu.addAction(i18n.t(key))
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, mode=mode: self.mode_selected.emit(mode))
            self.mode_group.addAction(action)
            self.mode_actions[mode] = action
        self.a_ca = m.addAction(i18n.t("conversational_awareness"))
        self.a_ca.setCheckable(True)
        self.a_ca.triggered.connect(lambda checked: self.ca_toggled.emit(bool(checked)))
        m.addSeparator()

        self.a_connect = m.addAction(i18n.t("connect"))
        self.a_connect.triggered.connect(self.connect_clicked.emit)
        self.a_disconnect = m.addAction(i18n.t("disconnect"))
        self.a_disconnect.triggered.connect(self.disconnect_clicked.emit)
        if sys.platform == "win32":
            self.a_connect.setVisible(False)
            self.a_disconnect.setVisible(False)

        self.device_menu = m.addMenu(i18n.t("device"))
        self.device_group = QActionGroup(self)
        self.device_actions: list[QAction] = []
        self.a_refresh = QAction(i18n.t("refresh"), self)
        self.a_refresh.triggered.connect(self.refresh_clicked.emit)
        self.update_devices([])

        self.a_settings_dialog = m.addAction(i18n.t("settings_dialog"))
        self.a_settings_dialog.triggered.connect(self.settings_clicked.emit)
        self.a_setup = m.addAction(i18n.t("setup"))
        self.a_setup.triggered.connect(self.setup_clicked.emit)
        self.settings_menu = m.addMenu(i18n.t("settings"))
        self.setting_actions: dict[str, QAction] = {}
        for key in SETTING_KEYS:
            action = self.settings_menu.addAction(i18n.t(key))
            action.setCheckable(True)
            action.setChecked(bool(getattr(self.settings, key)))
            action.triggered.connect(lambda checked, key=key: self.setting_toggled.emit(key, bool(checked)))
            self.setting_actions[key] = action
        m.addSeparator()

        self.a_show = m.addAction(i18n.t("show_battery"))
        self.a_show.triggered.connect(self.show_battery_clicked.emit)
        self.a_keys = m.addAction(i18n.t("fetch_keys"))
        self.a_keys.triggered.connect(self.fetch_keys_clicked.emit)
        if not sys.platform.startswith("linux"):
            self.a_keys.setVisible(False)
        m.addSeparator()
        self.a_about = m.addAction(i18n.t("about"))
        self.a_about.triggered.connect(self.about_clicked.emit)
        self.a_quit = m.addAction(i18n.t("quit"))
        self.a_quit.triggered.connect(self.quit_clicked.emit)

    def update_devices(self, devices: list[PairedDevice]) -> None:
        for action in self.device_actions:
            self.device_group.removeAction(action)
        self.device_actions.clear()
        self.device_menu.clear()  # deletes the menu-owned actions, so detach them from the group first
        if not devices:
            none = self.device_menu.addAction(i18n.t("none_paired"))
            none.setEnabled(False)
        for d in devices:
            label = f"{d.name}  ({d.model_name or d.address})"
            action = self.device_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(d.address.upper() == (self.settings.device_address or "").upper())
            action.triggered.connect(lambda checked=False, addr=d.address: self.bind_selected.emit(addr))
            self.device_group.addAction(action)
            self.device_actions.append(action)
        self.device_menu.addSeparator()
        self.device_menu.addAction(self.a_refresh)

    def sync_settings(self) -> None:
        for key, action in self.setting_actions.items():
            action.setChecked(bool(getattr(self.settings, key)))

    # ---- state -----------------------------------------------------------------------
    def update_state(self, state: DeviceState) -> None:
        self.state = state
        name = state.display_name if state.address else i18n.t("no_device")
        if state.address:
            status = i18n.t("connected") if state.connected else (i18n.t("out_of_range") if state.source == "none" else i18n.t("not_connected"))
            name = f"{name} – {status}"
        self.a_title.setText(name)
        self.a_levels.setText(state.levels_text() if state.has_battery else i18n.t("unknown"))
        self.a_levels.setVisible(state.has_battery)
        aap_live = state.aap_connected
        self.noise_menu.setEnabled(aap_live)
        for mode, action in self.mode_actions.items():
            action.setVisible(mode in state.allowed_modes)
            action.setChecked(state.noise_mode == mode)
        self.a_ca.setEnabled(aap_live and state.conversational_awareness is not None)
        self.a_ca.setChecked(bool(state.conversational_awareness))
        self.a_connect.setEnabled(bool(state.address) and not state.connected)
        self.a_disconnect.setEnabled(bool(state.address) and state.connected)
        self.a_keys.setEnabled(aap_live)
        self.a_keys.setVisible(sys.platform.startswith("linux") and not self.settings.keys_known)
        self.icon.setIcon(tray_icon(state, dark=True, show_percent=self.settings.tray_show_percent))
        tooltip = [name]
        if state.has_battery:
            tooltip.append(state.levels_text())
        self.icon.setToolTip("\n".join(tooltip))

    def notify(self, title: str, body: str, icon=QSystemTrayIcon.Information, msecs: int = 6000) -> None:
        if self.settings.notifications:
            self.icon.showMessage(title, body, icon, msecs)

    def _activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_battery_clicked.emit()
