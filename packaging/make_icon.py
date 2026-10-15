"""Draws the application icon: podsdesktop/gui/assets/icon.png (512 px) and packaging/podsdesktop.ico.
Run with the project venv: .venv/bin/python packaging/make_icon.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def draw(size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size
    bg = QLinearGradient(0, 0, s, s)
    bg.setColorAt(0, QColor("#2f6bff"))
    bg.setColorAt(1, QColor("#0b2f8a"))
    p.setPen(Qt.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.22, s * 0.22)

    def pod(cx: float, mirror: bool) -> None:
        path = QPainterPath()
        w, h = s * 0.19, s * 0.26
        head = QRectF(cx - w / 2, s * 0.24, w, h)
        path.addEllipse(head)
        stem_w = w * 0.42
        stem_x = cx - stem_w / 2 + (w * 0.18 if mirror else -w * 0.18)
        path.addRoundedRect(QRectF(stem_x, s * 0.42, stem_w, s * 0.34), stem_w / 2, stem_w / 2)
        p.setBrush(QColor("#f7f7fa"))
        p.setPen(QPen(QColor(0, 0, 0, 40), s * 0.01))
        p.drawPath(path.simplified())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#c9cbd3"))
        p.drawEllipse(QPointF(cx + (w * 0.22 if mirror else -w * 0.22), s * 0.36), w * 0.11, w * 0.11)

    pod(s * 0.36, False)
    pod(s * 0.64, True)
    # battery pill at the bottom
    p.setPen(QPen(QColor("#f7f7fa"), s * 0.025))
    p.setBrush(Qt.NoBrush)
    body = QRectF(s * 0.28, s * 0.80, s * 0.40, s * 0.11)
    p.drawRoundedRect(body, s * 0.03, s * 0.03)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#34c759"))
    p.drawRoundedRect(body.adjusted(s * 0.02, s * 0.02, -s * 0.14, -s * 0.02), s * 0.015, s * 0.015)
    p.setBrush(QColor("#f7f7fa"))
    p.drawRoundedRect(QRectF(body.right(), s * 0.825, s * 0.02, s * 0.06), s * 0.006, s * 0.006)
    p.end()
    return pix


def main() -> int:
    QGuiApplication(sys.argv)
    out_png = ROOT / "podsdesktop" / "gui" / "assets" / "icon.png"
    draw(512).save(str(out_png), "PNG")
    for size in (256, 128, 64, 48, 32, 16):
        draw(size).save(str(ROOT / "packaging" / f"icon-{size}.png"), "PNG")
    print("wrote", out_png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
