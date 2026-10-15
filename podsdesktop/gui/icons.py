"""Icons drawn with QPainter – no image assets to ship."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

from ..core.state import DeviceState

GREEN = QColor("#34c759")
YELLOW = QColor("#ffcc00")
RED = QColor("#ff3b30")
GRAY = QColor("#8e8e93")


def level_color(level: int | None) -> QColor:
    if level is None:
        return GRAY
    if level <= 20:
        return RED
    if level <= 40:
        return YELLOW
    return GREEN


def draw_battery(painter: QPainter, rect: QRectF, level: int | None, charging: bool, fg: QColor, vertical: bool = False) -> None:
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    stroke = max(1.5, rect.height() * 0.09 if not vertical else rect.width() * 0.09)
    painter.setPen(QPen(fg, stroke))
    painter.setBrush(Qt.NoBrush)
    if vertical:
        body = QRectF(rect.left(), rect.top() + rect.height() * 0.08, rect.width(), rect.height() * 0.92)
        nub = QRectF(rect.left() + rect.width() * 0.3, rect.top(), rect.width() * 0.4, rect.height() * 0.08)
    else:
        body = QRectF(rect.left(), rect.top(), rect.width() * 0.92, rect.height())
        nub = QRectF(body.right(), rect.top() + rect.height() * 0.3, rect.width() * 0.08, rect.height() * 0.4)
    radius = min(body.width(), body.height()) * 0.22
    painter.drawRoundedRect(body, radius, radius)
    painter.setPen(Qt.NoPen)
    painter.setBrush(fg)
    painter.drawRoundedRect(nub, 1.5, 1.5)
    inner = body.adjusted(stroke * 1.6, stroke * 1.6, -stroke * 1.6, -stroke * 1.6)
    if level is not None:
        fraction = max(0.0, min(1.0, level / 100))
        painter.setBrush(level_color(level))
        if vertical:
            h = inner.height() * fraction
            painter.drawRoundedRect(QRectF(inner.left(), inner.bottom() - h, inner.width(), h), 2, 2)
        else:
            painter.drawRoundedRect(QRectF(inner.left(), inner.top(), inner.width() * fraction, inner.height()), 2, 2)
    if charging:
        bolt = QPainterPath()
        cx, cy = body.center().x(), body.center().y()
        s = min(body.width(), body.height()) * 0.42
        bolt.moveTo(cx + s * 0.15, cy - s)
        bolt.lineTo(cx - s * 0.45, cy + s * 0.1)
        bolt.lineTo(cx - s * 0.02, cy + s * 0.1)
        bolt.lineTo(cx - s * 0.15, cy + s)
        bolt.lineTo(cx + s * 0.45, cy - s * 0.1)
        bolt.lineTo(cx + s * 0.02, cy - s * 0.1)
        bolt.closeSubpath()
        painter.setPen(QPen(QColor(0, 0, 0, 160), stroke * 0.6))
        painter.setBrush(QColor("#ffffff"))
        painter.drawPath(bolt)
    painter.restore()


def tray_icon(state: DeviceState | None, dark: bool = True, show_percent: bool = True, size: int = 64) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    fg = QColor("#f2f2f7") if dark else QColor("#1c1c1e")
    level = None
    charging = False
    if state is not None and state.has_battery:
        level = state.min_pod_level()
        if level is None:
            level = state.case.level
        charging = any(c.charging for c in (state.left, state.right))
    elif state is not None and not state.connected:
        fg.setAlpha(140)
    if show_percent and level is not None:
        draw_battery(painter, QRectF(size * 0.08, size * 0.06, size * 0.84, size * 0.44), level, charging, fg)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(int(size * 0.42))
        painter.setFont(font)
        painter.setPen(fg)
        painter.drawText(QRectF(0, size * 0.5, size, size * 0.5), Qt.AlignCenter, f"{level}")
    else:
        draw_battery(painter, QRectF(size * 0.08, size * 0.26, size * 0.84, size * 0.48), level, charging, fg)
        if level is None:
            painter.setPen(QPen(fg, size * 0.05))
            painter.drawLine(int(size * 0.3), int(size * 0.5), int(size * 0.62), int(size * 0.5))
    painter.end()
    return QIcon(pix)
