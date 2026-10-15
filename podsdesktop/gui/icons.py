"""Icons drawn with QPainter – no image assets to ship."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

from ..core.state import DeviceState
from . import theme


def draw_bolt(painter: QPainter, cx: float, cy: float, s: float, fill: QColor, outline: QColor | None = None) -> None:
    bolt = QPainterPath()
    bolt.moveTo(cx + s * 0.15, cy - s)
    bolt.lineTo(cx - s * 0.45, cy + s * 0.1)
    bolt.lineTo(cx - s * 0.02, cy + s * 0.1)
    bolt.lineTo(cx - s * 0.15, cy + s)
    bolt.lineTo(cx + s * 0.45, cy - s * 0.1)
    bolt.lineTo(cx + s * 0.02, cy - s * 0.1)
    bolt.closeSubpath()
    painter.save()
    painter.setPen(QPen(outline, max(1.0, s * 0.12)) if outline else Qt.NoPen)
    painter.setBrush(fill)
    painter.drawPath(bolt)
    painter.restore()


def draw_battery(painter: QPainter, rect: QRectF, level: int | None, charging: bool, fg: QColor,
                 vertical: bool = False, pal: theme.Palette | None = None, bolt: bool = True) -> None:
    """A rounded battery outline with a colour-coded fill; horizontal by default."""
    pal = pal or theme.palette()
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    thickness = rect.width() if vertical else rect.height()
    stroke = max(1.2, thickness * 0.09)
    painter.setPen(QPen(fg, stroke))
    painter.setBrush(Qt.NoBrush)
    if vertical:
        body = QRectF(rect.left(), rect.top() + rect.height() * 0.08, rect.width(), rect.height() * 0.92)
        nub = QRectF(rect.left() + rect.width() * 0.3, rect.top(), rect.width() * 0.4, rect.height() * 0.08)
    else:
        body = QRectF(rect.left(), rect.top(), rect.width() * 0.93, rect.height())
        nub = QRectF(body.right() + stroke * 0.6, rect.top() + rect.height() * 0.3, rect.width() * 0.05, rect.height() * 0.4)
    radius = min(body.width(), body.height()) * 0.26
    painter.drawRoundedRect(body, radius, radius)
    painter.setPen(Qt.NoPen)
    painter.setBrush(fg)
    painter.drawRoundedRect(nub, nub.width() * 0.4, nub.width() * 0.4)
    inner = body.adjusted(stroke * 1.7, stroke * 1.7, -stroke * 1.7, -stroke * 1.7)
    if level is not None:
        fraction = max(0.0, min(1.0, level / 100))
        painter.setBrush(theme.level_color(pal, level))
        r = min(inner.width(), inner.height()) * 0.3
        if vertical:
            h = max(inner.height() * fraction, r * 2 if fraction > 0 else 0)
            painter.drawRoundedRect(QRectF(inner.left(), inner.bottom() - h, inner.width(), h), r, r)
        else:
            w = max(inner.width() * fraction, r * 2 if fraction > 0 else 0)
            painter.drawRoundedRect(QRectF(inner.left(), inner.top(), w, inner.height()), r, r)
    if charging and bolt:
        draw_bolt(painter, body.center().x(), body.center().y(), min(body.width(), body.height()) * 0.42,
                  QColor("#ffffff"), QColor(0, 0, 0, 150))
    painter.restore()


def tray_icon(state: DeviceState | None, dark: bool | None = None, show_percent: bool = True, size: int = 64) -> QIcon:
    """Battery pill with the lowest pod level as a big number; dims when nothing is known."""
    dark = theme.is_dark() if dark is None else dark
    pal = theme.DARK if dark else theme.LIGHT
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
        fg.setAlpha(150)
    if show_percent and level is not None:
        draw_battery(painter, QRectF(size * 0.07, size * 0.05, size * 0.86, size * 0.42), level, charging, fg, pal=pal)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(int(size * 0.46))
        painter.setFont(font)
        painter.setPen(fg)
        painter.drawText(QRectF(0, size * 0.47, size, size * 0.53), Qt.AlignCenter, f"{level}")
    else:
        draw_battery(painter, QRectF(size * 0.07, size * 0.27, size * 0.86, size * 0.46), level, charging, fg, pal=pal)
        if level is None:
            painter.setPen(QPen(fg, size * 0.05, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(int(size * 0.3), int(size * 0.5), int(size * 0.62), int(size * 0.5))
    painter.end()
    return QIcon(pix)
