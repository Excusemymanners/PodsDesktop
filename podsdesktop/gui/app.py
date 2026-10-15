"""Wires the engine, the tray, the popup, the setup assistant and the notifications together."""

from __future__ import annotations

import logging
import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QSystemTrayIcon

from .. import __version__
from ..core import autostart
from ..core.engine import Engine
from ..core.settings import Settings
from ..core.state import Component, DeviceState
from ..protocol import aap
from . import i18n, images, theme
from .bridge import EngineBridge
from .low_latency import SilenceKeeper
from .popup import BatteryPopup
from .settings_dialog import SettingsDialog
from .tray import Tray
from .wizard import SetupWizard

log = logging.getLogger(__name__)


class PodsApp:
    def __init__(self, settings: Settings, force_setup: bool = False, preview: str | None = None,
                 snapshot: str | None = None):
        self.settings = settings
        self.force_setup = force_setup
        self.preview = preview
        self.snapshot = snapshot
        i18n.set_language(settings.language)
        self.qt = QApplication.instance() or QApplication(sys.argv)
        self.qt.setApplicationName("PodsDesktop")
        self.qt.setWindowIcon(images.app_icon())
        self.qt.setQuitOnLastWindowClosed(False)
        self.qt.setStyleSheet(theme.stylesheet(theme.palette()))
        self.engine = Engine(settings)
        self.bridge = EngineBridge(self.engine)
        self.bridge.event.connect(self.on_event)
        self.tray = Tray(settings)
        self.popup = BatteryPopup(settings.popup_seconds)
        self.silence = SilenceKeeper()
        self.state: DeviceState | None = None
        self.wizard: SetupWizard | None = None
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
        t.setup_clicked.connect(self.open_wizard)
        t.settings_clicked.connect(self.open_settings)
        t.about_clicked.connect(self.show_about)
        t.quit_clicked.connect(self.quit)
        if not getattr(self, "_popup_wired", False):
            self._popup_wired = True
            self.popup.mode_selected.connect(lambda mode: self.bridge.call(self.engine.set_noise_mode(mode)))
            self.popup.connect_clicked.connect(lambda: self.bridge.call(self.engine.connect_device()))

    # ---- events from the engine ------------------------------------------------------
    def on_event(self, name: str, payload) -> None:
        if self.wizard is not None:
            self.wizard.on_event(name, payload)
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

    # ---- settings ----------------------------------------------------------------------
    def on_setting_toggled(self, key: str, value: bool) -> None:
        setattr(self.settings, key, value)
        self._apply_settings()

    def _apply_settings(self) -> None:
        try:
            if self.settings.autostart != autostart.is_enabled():
                autostart.set_enabled(self.settings.autostart)
        except Exception as exc:  # noqa: BLE001
            self.tray.notify(i18n.t("error"), str(exc), QSystemTrayIcon.Warning)
            self.settings.autostart = autostart.is_enabled()
        self.bridge.call(self.engine.apply_settings())
        self.popup.seconds = self.settings.popup_seconds
        self.tray.sync_settings()
        if self.state:
            self.tray.update_state(self.state)
        self._apply_low_latency()

    def _apply_low_latency(self) -> None:
        want = self.settings.low_latency and self.state is not None and self.state.connected
        if want:
            self.silence.start()
        else:
            self.silence.stop()

    def _rebuild_tray(self) -> None:
        i18n.set_language(self.settings.language)
        self.tray.icon.hide()
        self.tray = Tray(self.settings)
        self._wire()
        self.tray.update_devices(self.engine.devices)
        if self.state:
            self.tray.update_state(self.state)
        self.tray.icon.show()

    # ---- windows -----------------------------------------------------------------------
    def show_popup(self) -> None:
        """Tray click: toggle. A click on the icon while the popup is open closes it (the popup
        closes itself on the outside click, so the activation that follows must not reopen it)."""
        if self.popup.isVisible():
            self.popup.hide_animated()
            return
        if self.popup.recently_hidden():
            return
        if self.state is not None:
            self.popup.update_state(self.state)
        self.popup.show_for(interactive=True)

    def open_wizard(self) -> None:
        if self.wizard is not None:
            self.wizard.raise_()
            self.wizard.activateWindow()
            return
        i18n.set_language(self.settings.language)
        wizard = SetupWizard(self.settings, self.state)
        wizard.requested.connect(self.on_wizard_request)
        wizard.language_changed.connect(self.on_language_changed)
        wizard.finished_setup.connect(self.on_setup_finished)
        wizard.finished.connect(self._wizard_closed)
        self.wizard = wizard
        wizard.show()
        wizard.raise_()
        wizard.activateWindow()

    def on_wizard_request(self, what: str, payload) -> None:
        if what == "adapter":
            self.bridge.call(self.engine.adapter_status())
        elif what == "power_on":
            self.bridge.call(self.engine.power_on())
        elif what == "devices":
            self.bridge.call(self.engine.refresh_devices())
        elif what == "bind":
            self.bridge.call(self.engine.bind(payload))

    def on_language_changed(self, code: str) -> None:
        self.settings.save()
        self._rebuild_tray()
        if self.wizard is not None:
            old = self.wizard
            self.wizard = None
            old.finished.disconnect(self._wizard_closed)
            old.close()
            old.deleteLater()
            self.open_wizard()

    def on_setup_finished(self) -> None:
        self._apply_settings()
        if self.settings.language in ("ro", "en") and self.settings.language != i18n.current_language():
            self._rebuild_tray()

    def _wizard_closed(self, *_args) -> None:
        self.wizard = None

    def open_settings(self) -> None:
        i18n.set_language(self.settings.language)
        dialog = SettingsDialog(self.settings, self.engine.devices)
        self._settings_dialog = dialog
        dialog.run_setup.clicked.connect(lambda: (dialog.reject(), self.open_wizard()))
        accepted = dialog.exec() == QDialog.Accepted
        self._settings_dialog = None
        if not accepted:
            return
        old_language = i18n.current_language()
        dialog.apply()
        if dialog.keys_changed:
            self.settings.save()
            if self.state:
                self.tray.update_state(self.state)
        address = dialog.selected_address()
        if address != self.settings.device_address:
            self.bridge.call(self.engine.bind(address))
        self._apply_settings()
        i18n.set_language(self.settings.language)
        if i18n.current_language() != old_language:
            self._rebuild_tray()

    def show_about(self) -> None:
        QMessageBox.information(None, i18n.t("about"),
                                f"PodsDesktop {__version__}\n\nAirPods on Linux and Windows: battery, ear detection, noise control.\n"
                                "Protocol work based on AirPodsDesktop, LibrePods and zeffd/airpods.\nGPL-3.0")

    def quit(self) -> None:
        self.silence.stop()
        self.bridge.stop()
        self.qt.quit()

    def run_preview(self) -> int:
        """Design/screenshot mode: demo data, no radio, no engine thread."""
        demo_address = self.settings.device_address or "00:11:22:33:44:55"
        state = DeviceState(address=demo_address, name="Luca’s AirPods Pro", model_id=0x2014, firmware="7B19",
                            left=Component(87, True, False, True, True), right=Component(85, False, True, True, True),
                            case=Component(60, False, False, True, True), connected=True, aap_connected=True,
                            noise_mode=aap.MODE_ANC, allowed_modes=[1, 2, 3, 4], conversational_awareness=True, source="aap")
        self.state = state
        self.tray.icon.show()
        self.tray.update_state(state)
        self.popup.update_state(state)
        if self.preview == "settings":
            from ..core.bluetooth import PairedDevice

            self.engine.devices = [PairedDevice(demo_address, "Luca’s AirPods Pro", 0x004C, 0x2014, True)]
            QTimer.singleShot(300, self.open_settings)
        else:
            import os

            self.popup.show_for(120, interactive=os.environ.get("PODSDESKTOP_PREVIEW_INTERACTIVE") == "1")
        if self.force_setup:
            from ..core.bluetooth import PairedDevice

            demo_devices = [PairedDevice(demo_address, "Luca’s AirPods Pro", 0x004C, 0x2014, True),
                            PairedDevice("00:11:22:33:44:66", "AirPods Max", 0x004C, 0x202D, False)]
            QTimer.singleShot(300, self.open_wizard)
            QTimer.singleShot(1200, lambda: self.wizard and self.wizard.on_event("adapter", True))
            QTimer.singleShot(1300, lambda: self.wizard and self.wizard.on_event("devices", demo_devices))
        log.info(i18n.t("preview_hint"))

        def report_geometry() -> None:
            screen = self.qt.primaryScreen()
            dpr = screen.devicePixelRatio() if screen else 1.0
            for name, widget in (("popup", self.popup), ("wizard", self.wizard), ("settings", getattr(self, "_settings_dialog", None))):
                if widget is not None and widget.isVisible():
                    g = widget.frameGeometry()
                    log.info("preview geometry %s: x=%d y=%d w=%d h=%d dpr=%.2f", name, g.x(), g.y(), g.width(), g.height(), dpr)

        QTimer.singleShot(2500, report_geometry)

        def take_snapshot() -> None:
            target = {"wizard": self.wizard, "settings": getattr(self, "_settings_dialog", None)}.get(self.preview, self.popup)
            if target is None:
                log.warning("snapshot: window not ready")
            else:
                target.grab().save(self.snapshot)
                log.info("snapshot written to %s", self.snapshot)
            if getattr(self, "_settings_dialog", None) is not None:
                self._settings_dialog.reject()
            self.qt.quit()

        if self.snapshot:
            QTimer.singleShot(1800, take_snapshot)
        signal.signal(signal.SIGINT, lambda *_: self.qt.quit())
        keepalive = QTimer()
        keepalive.timeout.connect(lambda: None)
        keepalive.start(250)
        return self.qt.exec()

    def run(self) -> int:
        if self.preview:
            return self.run_preview()
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
        if self.force_setup or not self.settings.setup_done:
            QTimer.singleShot(800, self.open_wizard)
        return self.qt.exec()


def run_gui(settings: Settings, force_setup: bool = False, preview: str | None = None, snapshot: str | None = None) -> int:
    return PodsApp(settings, force_setup=force_setup, preview=preview, snapshot=snapshot).run()
