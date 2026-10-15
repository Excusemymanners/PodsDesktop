"""Wires the engine, the tray, the popup and the notifications together."""

from __future__ import annotations

import logging
import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .. import __version__
from ..core import autostart
from ..core.engine import Engine
from ..core.settings import Settings
from ..core.state import DeviceState
from ..protocol import aap
from . import i18n
from .bridge import EngineBridge
from .low_latency import SilenceKeeper
from .popup import BatteryPopup
from .tray import Tray

log = logging.getLogger(__name__)


class PodsApp:
    def __init__(self, settings: Settings):
        self.settings = settings
        i18n.set_language(settings.language)
        self.qt = QApplication.instance() or QApplication(sys.argv)
        self.qt.setApplicationName("PodsDesktop")
        self.qt.setQuitOnLastWindowClosed(False)
        self.engine = Engine(settings)
        self.bridge = EngineBridge(self.engine)
        self.bridge.event.connect(self.on_event)
        self.tray = Tray(settings)
        self.popup = BatteryPopup(settings.popup_seconds)
        self.silence = SilenceKeeper()
        self.state: DeviceState | None = None
        self._wire()

    def _wire(self) -> None:
        t = self.tray
        t.mode_selected.connect(lambda mode: self.bridge.call(self.engine.set_noise_mode(mode)))
        t.ca_toggled.connect(lambda on: self.bridge.call(self.engine.set_toggle(aap.CTL_CONVERSATIONAL_AWARENESS, on)))
        t.connect_clicked.connect(lambda: self.bridge.call(self.engine.connect_device()))
        t.disconnect_clicked.connect(lambda: self.bridge.call(self.engine.disconnect_device()))
        t.bind_selected.connect(lambda addr: self.bridge.call(self.engine.bind(addr)))
        t.refresh_clicked.connect(lambda: self.bridge.call(self.engine.refresh_devices()))
        t.setting_toggled.connect(self.on_setting_toggled)
        t.show_battery_clicked.connect(self.show_popup)
        t.fetch_keys_clicked.connect(lambda: self.bridge.call(self.engine.fetch_keys()))
        t.about_clicked.connect(self.show_about)
        t.quit_clicked.connect(self.quit)

    # ---- events from the engine ------------------------------------------------------
    def on_event(self, name: str, payload) -> None:
        if name == "state":
            self.state = payload
            self.tray.update_state(payload)
            self.popup.update_state(payload)
        elif name == "lid":
            if payload and self.settings.popup_on_lid and self.state is not None:
                self.popup.show_for()
            elif not payload:
                self.popup.hide()
        elif name == "connection":
            name_ = self.state.display_name if self.state else "AirPods"
            self.tray.notify("PodsDesktop", i18n.t("notify_connected" if payload else "notify_disconnected", name=name_))
            self._apply_low_latency()
        elif name == "low_battery":
            name_ = self.state.display_name if self.state else "AirPods"
            self.tray.notify(i18n.t("notify_low_title"), i18n.t("notify_low_body", name=name_, level=payload), QSystemTrayIcon.Warning)
        elif name == "keys":
            self.tray.notify("PodsDesktop", i18n.t("notify_keys"))
            if self.state:
                self.tray.update_state(self.state)
        elif name == "devices":
            self.tray.update_devices(payload)
        elif name == "error":
            log.warning("%s", payload)
            self.tray.notify(i18n.t("error"), str(payload), QSystemTrayIcon.Warning)

    def on_setting_toggled(self, key: str, value: bool) -> None:
        setattr(self.settings, key, value)
        if key == "autostart":
            try:
                autostart.set_enabled(value)
            except Exception as exc:  # noqa: BLE001
                self.tray.notify(i18n.t("error"), str(exc), QSystemTrayIcon.Warning)
                self.settings.autostart = autostart.is_enabled()
                self.tray.sync_settings()
        self.bridge.call(self.engine.apply_settings())
        if key == "low_latency":
            self._apply_low_latency()

    def _apply_low_latency(self) -> None:
        want = self.settings.low_latency and self.state is not None and self.state.connected
        if want:
            self.silence.start()
        else:
            self.silence.stop()

    def show_popup(self) -> None:
        if self.state is not None:
            self.popup.update_state(self.state)
        self.popup.show_for()

    def show_about(self) -> None:
        QMessageBox.information(None, i18n.t("about"),
                                f"PodsDesktop {__version__}\n\nAirPods on Linux and Windows: battery, ear detection, noise control.\n"
                                "Protocol work based on AirPodsDesktop, LibrePods and zeffd/airpods.\nGPL-3.0")

    def quit(self) -> None:
        self.silence.stop()
        self.bridge.stop()
        self.qt.quit()

    def run(self) -> int:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning(i18n.t("tray_unavailable"))
        self.tray.icon.show()
        self.settings.autostart = autostart.is_enabled()
        self.tray.sync_settings()
        self.bridge.start()
        signal.signal(signal.SIGINT, lambda *_: self.quit())
        keepalive = QTimer()
        keepalive.timeout.connect(lambda: None)
        keepalive.start(250)  # lets Python handle SIGINT while Qt is idle
        return self.qt.exec()


def run_gui(settings: Settings) -> int:
    return PodsApp(settings).run()
