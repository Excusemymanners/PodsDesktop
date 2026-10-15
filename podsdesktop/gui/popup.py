"""The battery window: shows up when the case opens, on a tray click, or from the menu.

Layout (iOS-like): name + status, the product picture, one card per battery (label, big
percentage, horizontal battery), the noise-control segmented control while an AAP session is
live, and a connect button while the pods are paired but not connected. Follows the system's
light/dark scheme, fades in and out, and does not auto-hide while the pointer is over it.
"""

from __future__ import annotations

import sys
import time

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QButtonGroup, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..core.state import Component, DeviceState
from ..protocol import aap
from . import i18n, images, theme
from .icons import draw_battery

MODE_KEYS = {aap.MODE_OFF: "mode_off", aap.MODE_ANC: "mode_anc", aap.MODE_TRANSPARENCY: "mode_transparency", aap.MODE_ADAPTIVE: "mode_adaptive"}
MODE_SHORT = {aap.MODE_OFF: "mode_off", aap.MODE_ANC: "mode_anc_short", aap.MODE_TRANSPARENCY: "mode_transparency_short", aap.MODE_ADAPTIVE: "mode_adaptive"}


class BatteryCard(QWidget):
    def __init__(self, label_key: str, parent=None):
        super().__init__(parent)
        self.label_key = label_key
        self.component = Component()
        self.pal = theme.palette()
        self.setMinimumSize(104, 112)

    def set_component(self, component: Component, pal: theme.Palette) -> None:
        self.component = component
        self.pal = pal
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.pal
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(pal.card))
        p.drawRoundedRect(QRectF(0, 0, w, h), 14, 14)
        comp = self.component
        text = QColor(pal.text)
        dim = QColor(pal.dim)
        if not comp.available:
            text.setAlpha(120)
        font = QFont()
        font.setPixelSize(12)
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        p.setPen(dim)
        label = i18n.t(self.label_key)
        p.drawText(QRectF(12, 10, w - 24, 18), Qt.AlignLeft | Qt.AlignVCenter, label)
        if comp.in_ear:
            p.setBrush(QColor(pal.accent))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(w - 20, 15, 8, 8))
        font.setPixelSize(24)
        font.setWeight(QFont.Bold)
        p.setFont(font)
        p.setPen(text)
        value = f"{comp.level}%" if comp.available and comp.level is not None else i18n.t("unknown")
        p.drawText(QRectF(12, 32, w - 24, 34), Qt.AlignLeft | Qt.AlignVCenter, value)
        draw_battery(p, QRectF(12, h - 34, w - 24 - 6, 20), comp.level if comp.available else None, comp.charging, text, pal=pal)
        p.end()


class BatteryPopup(QWidget):
    mode_selected = Signal(int)
    connect_clicked = Signal()

    PASSIVE_FLAGS = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
    INTERACTIVE_FLAGS = Qt.Popup | Qt.FramelessWindowHint

    def __init__(self, seconds: int = 10):
        flags = self.PASSIVE_FLAGS
        if sys.platform.startswith("linux"):
            flags |= Qt.X11BypassWindowManagerHint  # never a taskbar entry, placed exactly where asked
        super().__init__(None, flags)
        self.setObjectName("podsPopup")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.seconds = seconds
        self.interactive = False
        self.hidden_at = 0.0
        self.pal = theme.palette()
        self._hover = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._auto_hide)
        self.panel = _Panel(self)
        self.effect = QGraphicsOpacityEffect(self.panel)
        self.effect.setOpacity(1.0)
        self.panel.setGraphicsEffect(self.effect)
        self._fade = QPropertyAnimation(self.effect, b"opacity", self)
        self._fade.setDuration(170)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)

        self.title = QLabel("AirPods")
        self.subtitle = QLabel("")
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(26, 26)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.clicked.connect(self.hide_animated)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(1)
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)
        header.addWidget(self.close_button, 0, Qt.AlignTop)

        self.image = QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setPixmap(images.model_pixmap(None, 104))

        self.cards = {"left": BatteryCard("left"), "right": BatteryCard("right"), "case": BatteryCard("case")}
        cards = QHBoxLayout()
        cards.setSpacing(8)
        for card in self.cards.values():
            cards.addWidget(card)

        self.modes_label = QLabel(i18n.t("noise_control"))
        self.mode_group = QButtonGroup(self)
        self.mode_buttons: dict[int, QPushButton] = {}
        modes = QHBoxLayout()
        modes.setSpacing(4)
        for mode, key in MODE_SHORT.items():
            button = QPushButton(i18n.t(key))
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, mode=mode: self.mode_selected.emit(mode))
            self.mode_group.addButton(button)
            self.mode_buttons[mode] = button
            modes.addWidget(button)
        self.modes_widget = QWidget()
        modes_layout = QVBoxLayout(self.modes_widget)
        modes_layout.setContentsMargins(0, 4, 0, 0)
        modes_layout.setSpacing(4)
        modes_layout.addWidget(self.modes_label)
        modes_layout.addLayout(modes)

        self.connect_button = QPushButton(i18n.t("connect"))
        self.connect_button.setCursor(Qt.PointingHandCursor)
        self.connect_button.clicked.connect(self.connect_clicked.emit)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.panel)
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(self.image)
        layout.addLayout(cards)
        layout.addWidget(self.modes_widget)
        layout.addWidget(self.connect_button)
        self.modes_widget.hide()
        self.connect_button.hide()
        self.setFixedWidth(392)
        self._apply_theme()

    # ---- theme -------------------------------------------------------------------------
    def _apply_theme(self) -> None:
        pal = self.pal = theme.palette()
        self.title.setStyleSheet(f"color: {pal.text}; font-size: 17px; font-weight: 700; background: transparent;")
        self.subtitle.setStyleSheet(f"color: {pal.dim}; font-size: 12px; background: transparent;")
        self.modes_label.setStyleSheet(f"color: {pal.dim}; font-size: 12px; font-weight: 600; background: transparent;")
        self.close_button.setStyleSheet(
            f"QPushButton {{ color: {pal.dim}; background: {pal.card}; border: 0; border-radius: 13px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {pal.card_hover}; color: {pal.text}; }}")
        seg = (f"QPushButton {{ color: {pal.text}; background: {pal.card}; border: 0; border-radius: 9px; padding: 7px 4px; font-size: 12px; }}"
               f"QPushButton:hover {{ background: {pal.card_hover}; }}"
               f"QPushButton:checked {{ background: {pal.accent}; color: white; font-weight: 600; }}")
        for button in self.mode_buttons.values():
            button.setStyleSheet(seg)
        self.connect_button.setStyleSheet(
            f"QPushButton {{ color: white; background: {pal.accent}; border: 0; border-radius: 10px; padding: 9px; font-size: 13px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {pal.accent}; }}")

    # ---- content -----------------------------------------------------------------------
    def update_state(self, state: DeviceState) -> None:
        if theme.is_dark() != self.pal.dark:
            self._apply_theme()
        self.title.setText(state.display_name)
        self.image.setPixmap(images.model_pixmap(state.model_id, 104))
        if state.is_headset:
            self.cards["left"].label_key = "battery"
            self.cards["right"].hide()
            self.cards["case"].hide()
        else:
            self.cards["left"].label_key = "left"
            self.cards["right"].show()
            self.cards["case"].show()
        self.cards["left"].set_component(state.left, self.pal)
        self.cards["right"].set_component(state.right, self.pal)
        self.cards["case"].set_component(state.case, self.pal)
        src = {"aap": "source_aap", "ble": "source_ble", "ble-exact": "source_ble_exact"}.get(state.source)
        bits = [i18n.t("connected") if state.connected else i18n.t("not_connected")]
        if src:
            bits.append(i18n.t(src))
        if state.firmware:
            bits.append(state.firmware)
        self.subtitle.setText(" · ".join(bits))
        live = state.aap_connected
        self.modes_widget.setVisible(live)
        if live:
            for mode, button in self.mode_buttons.items():
                button.setVisible(mode in state.allowed_modes)
                button.setChecked(state.noise_mode == mode)
        self.connect_button.setVisible(bool(state.address) and not state.connected and sys.platform.startswith("linux"))
        self.adjustSize()

    # ---- showing / hiding --------------------------------------------------------------
    def _set_mode(self, interactive: bool) -> None:
        """Passive: a tool window that never takes focus (case opened). Interactive: a real
        popup like the Wi-Fi menu, closed by any click outside it (tray icon click)."""
        if interactive == self.interactive and self.windowHandle() is not None:
            return
        flags = self.INTERACTIVE_FLAGS if interactive else self.PASSIVE_FLAGS
        if not interactive and sys.platform.startswith("linux"):
            flags |= Qt.X11BypassWindowManagerHint
        was_visible = self.isVisible()
        if was_visible:
            self.hide()
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_ShowWithoutActivating, not interactive)
        self.interactive = interactive

    def show_for(self, seconds: int | None = None, interactive: bool = False) -> None:
        self._set_mode(interactive)
        self.adjustSize()
        self._place()
        self._fade.stop()
        if not self.isVisible():
            self.effect.setOpacity(0.0)
            self.show()
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()
        else:
            self.effect.setOpacity(1.0)
        self.raise_()
        if interactive:
            self._timer.stop()  # stays until a click outside or the close button
        else:
            self._timer.start(int((seconds or self.seconds) * 1000))

    def recently_hidden(self, within: float = 0.5) -> bool:
        return (time.monotonic() - self.hidden_at) < within

    def hideEvent(self, event) -> None:  # noqa: N802
        self.hidden_at = time.monotonic()
        super().hideEvent(event)

    def hide_animated(self) -> None:
        if not self.isVisible():
            return
        self._timer.stop()
        self._fade.stop()
        self._fade.setStartValue(self.effect.opacity())
        self._fade.setEndValue(0.0)
        try:
            self._fade.finished.disconnect(self._finish_hide)
        except (RuntimeError, TypeError):
            pass
        self._fade.finished.connect(self._finish_hide)
        self._fade.start()

    def _finish_hide(self) -> None:
        try:
            self._fade.finished.disconnect(self._finish_hide)
        except (RuntimeError, TypeError):
            pass
        if self._fade.endValue() == 0.0:
            self.hide()
            self.effect.setOpacity(1.0)

    def _auto_hide(self) -> None:
        if self._hover:
            self._timer.start(2000)
            return
        self.hide_animated()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        if self.isVisible() and not self._timer.isActive():
            self._timer.start(2000)

    def _place(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 18, area.bottom() - self.height() - 18)



class _Panel(QWidget):
    """The rounded, slightly translucent sheet everything sits on (fades via a graphics effect)."""

    def __init__(self, popup: "BatteryPopup"):
        super().__init__(popup)
        self.popup = popup
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:  # noqa: N802
        pal = self.popup.pal
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QColor(pal.bg)
        bg.setAlpha(244)
        p.setPen(QPen(QColor(255, 255, 255, 28) if pal.dark else QColor(0, 0, 0, 24), 1))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 20, 20)
        p.end()
