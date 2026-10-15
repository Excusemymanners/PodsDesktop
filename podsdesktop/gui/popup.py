"""The little window that shows up when the case opens (and on tray click)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..core.state import Component, DeviceState
from . import i18n, images
from .icons import draw_battery

BG = QColor(28, 28, 30, 235)
FG = QColor("#f2f2f7")
DIM = QColor("#aeaeb2")


class ComponentView(QWidget):
    def __init__(self, label_key: str, parent=None):
        super().__init__(parent)
        self.label_key = label_key
        self.component = Component()
        self.setMinimumSize(96, 112)

    def set_component(self, component: Component) -> None:
        self.component = component
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        comp = self.component
        fg = QColor(FG)
        if not comp.available:
            fg.setAlpha(110)
        draw_battery(p, QRectF(w * 0.34, 6, w * 0.32, h * 0.46), comp.level if comp.available else None, comp.charging, fg, vertical=True)
        font = QFont()
        font.setPixelSize(20)
        font.setBold(True)
        p.setFont(font)
        p.setPen(fg)
        p.drawText(QRectF(0, h * 0.52, w, 28), Qt.AlignCenter, comp.text(i18n.t("unknown")).replace(" ⚡", ""))
        font.setPixelSize(12)
        font.setBold(False)
        p.setFont(font)
        p.setPen(DIM)
        label = i18n.t(self.label_key)
        if comp.in_ear:
            label += " · " + i18n.t("in_ear")
        elif comp.charging:
            label += " · ⚡"
        p.drawText(QRectF(0, h * 0.52 + 30, w, 20), Qt.AlignCenter, label)
        p.end()


class BatteryPopup(QWidget):
    def __init__(self, seconds: int = 10):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.seconds = seconds
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.title = QLabel("AirPods")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("color: #f2f2f7; font-size: 15px; font-weight: 600;")
        self.subtitle = QLabel("")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setStyleSheet("color: #aeaeb2; font-size: 11px;")
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setPixmap(images.model_pixmap(None, 96))
        self.views = {"left": ComponentView("left"), "right": ComponentView("right"), "case": ComponentView("case")}
        row = QHBoxLayout()
        row.setSpacing(4)
        for view in self.views.values():
            row.addWidget(view)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 12)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.image)
        layout.addLayout(row)
        self.resize(360, 300)

    def update_state(self, state: DeviceState) -> None:
        self.title.setText(state.display_name)
        self.image.setPixmap(images.model_pixmap(state.model_id, 96))
        if state.is_headset:
            self.views["left"].label_key = "battery"
            self.views["right"].hide()
            self.views["case"].hide()
        else:
            self.views["left"].label_key = "left"
            self.views["right"].show()
            self.views["case"].show()
        self.views["left"].set_component(state.left)
        self.views["right"].set_component(state.right)
        self.views["case"].set_component(state.case)
        src = {"aap": "source_aap", "ble": "source_ble", "ble-exact": "source_ble_exact"}.get(state.source)
        bits = [i18n.t("connected") if state.connected else i18n.t("not_connected")]
        if src:
            bits.append(i18n.t(src))
        if state.firmware:
            bits.append(state.firmware)
        self.subtitle.setText(" · ".join(bits))

    def show_for(self, seconds: int | None = None) -> None:
        self._place()
        self.show()
        self.raise_()
        self._timer.start(int((seconds or self.seconds) * 1000))

    def _place(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 16, area.bottom() - self.height() - 16)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.hide()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(BG)
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)
        p.end()
