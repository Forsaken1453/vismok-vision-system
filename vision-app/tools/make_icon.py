# -*- coding: utf-8 -*-
"""Buat ikon aplikasi VISMOK secara programatik (rounded tile navy +
ikan geometris cyan + bracket scan vision) -> PNG 1024 & ICO multi-size.
"""
import math
import os

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QIcon,
                           QLinearGradient, QPainter, QPainterPath,
                           QPen, QPolygonF, QImage)
from PySide6.QtWidgets import QApplication

_app = QApplication([])

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PNG = os.path.join(BASE, "assets", "img", "app_icon_1024.png")
OUT_ICO = os.path.join(BASE, "assets", "img", "app.ico")

for f in os.listdir(os.path.join(BASE, "assets", "fonts")):
    QFontDatabase.addApplicationFont(os.path.join(BASE, "assets", "fonts", f))

S = 1024
pm = QImage(S, S, QImage.Format_ARGB32)
pm.fill(Qt.transparent)
p = QPainter(pm)
p.setRenderHint(QPainter.Antialiasing)
p.setRenderHint(QPainter.TextAntialiasing)

# ---------- tile: rounded square, gradasi navy dalam ----------
r = 232
tile = QRectF(16, 16, S - 32, S - 32)
grad = QLinearGradient(tile.topLeft(), tile.bottomRight())
grad.setColorAt(0.0, QColor("#12283F"))
grad.setColorAt(0.5, QColor("#0B1B2B"))
grad.setColorAt(1.0, QColor("#071019"))
p.setPen(Qt.NoPen)
p.setBrush(QBrush(grad))
p.drawRoundedRect(tile, r, r)

# rim halus
p.setBrush(Qt.NoBrush)
p.setPen(QPen(QColor(34, 211, 238, 70), 6))
p.drawRoundedRect(tile.adjusted(3, 3, -3, -3), r, r)

cx, cy = S / 2, S / 2 - 20

# ---------- bracket scan (sudut, gaya vision) ----------
bw, bl, off = 8.0, 110.0, 96.0
p.setPen(QPen(QColor("#22D3EE"), bw, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
    x = S / 2 + sx * (S / 2 - off - 60)
    y = S / 2 + sy * (S / 2 - off - 60)
    dx, dy = -sx, -sy
    path = QPainterPath()
    path.moveTo(x + dx * bl, y)
    path.lineTo(x, y)
    path.lineTo(x, y + dy * bl)
    p.drawPath(path)

# ---------- ikan geometris (siluet futuristik) ----------
body_grad = QLinearGradient(cx - 300, cy - 160, cx + 300, cy + 160)
body_grad.setColorAt(0.0, QColor("#7DF3FF"))
body_grad.setColorAt(0.55, QColor("#22D3EE"))
body_grad.setColorAt(1.0, QColor("#0891B2"))
body = QPainterPath()
# badan: bentuk fusiform panjang (hidung kiri -> ekor kanan)
body.moveTo(cx - 330, cy)
body.cubicTo(cx - 240, cy - 150, cx + 40, cy - 175, cx + 215, cy - 55)
body.cubicTo(cx + 250, cy - 75, cx + 300, cy - 110, cx + 330, cy - 120)
body.lineTo(cx + 245, cy)
body.lineTo(cx + 330, cy + 120)
body.cubicTo(cx + 300, cy + 110, cx + 250, cy + 75, cx + 215, cy + 55)
body.cubicTo(cx + 40, cy + 175, cx - 240, cy + 150, cx - 330, cy)
body.closeSubpath()
p.setPen(Qt.NoPen)
p.setBrush(QBrush(body_grad))
p.drawPath(body)

# sirip atas & bawah (gelap semi transparan)
fin = QPolygonF([
    QPointF(cx - 60, cy - 168), QPointF(cx + 60, cy - 190),
    QPointF(cx + 40, cy - 118), QPointF(cx - 90, cy - 128),
])
p.setBrush(QBrush(QColor(8, 60, 82, 220)))
p.drawPolygon(fin)
fin2 = QPolygonF([
    QPointF(cx - 40, cy + 150), QPointF(cx + 55, cy + 168),
    QPointF(cx + 25, cy + 108), QPointF(cx - 80, cy + 118),
])
p.drawPolygon(fin2)

# ekor: segitiga terpisah dgn celah (futuristik)
tail = QPolygonF([
    QPointF(cx + 352, cy - 128), QPointF(cx + 452, cy - 178),
    QPointF(cx + 402, cy), QPointF(cx + 452, cy + 178),
    QPointF(cx + 352, cy + 128), QPointF(cx + 392, cy),
])
tail_grad = QLinearGradient(cx + 352, cy, cx + 452, cy)
tail_grad.setColorAt(0.0, QColor("#22D3EE"))
tail_grad.setColorAt(1.0, QColor("#67E8F9"))
p.setBrush(QBrush(tail_grad))
p.drawPolygon(tail)

# mata
p.setBrush(QBrush(QColor("#0B1B2B")))
p.drawEllipse(QPointF(cx - 235, cy - 32), 26, 26)
p.setBrush(QBrush(QColor("#EAF6FF")))
p.drawEllipse(QPointF(cx - 240, cy - 38), 9, 9)

# garis aksen di badan (gaya sirkuit)
p.setPen(QPen(QColor(234, 246, 255, 110), 6, Qt.SolidLine, Qt.RoundCap))
for i, dy in enumerate((-52, 0, 52)):
    x1 = cx - 180 + abs(dy)
    x2 = cx + 130 - abs(dy)
    p.drawLine(QPointF(x1, cy + dy), QPointF(x2, cy + dy))
    p.drawEllipse(QPointF(x2 + 16, cy + dy), 10, 10)

# ---------- teks brand ----------
f = QFont("Orbitron", 44)
f.setBold(True)
f.setLetterSpacing(QFont.AbsoluteSpacing, 10.0)
p.setFont(f)
p.setPen(QColor("#EAF6FF"))
tw = p.fontMetrics().horizontalAdvance("VISMOK")
p.drawText(QRectF(0, S - 176, S, 90), Qt.AlignHCenter | Qt.AlignVCenter,
           "VISMOK")
p.setPen(QColor("#22D3EE"))
f2 = QFont("Rajdhani", 20)
f2.setBold(True)
f2.setLetterSpacing(QFont.AbsoluteSpacing, 7.0)
p.setFont(f2)
p.drawText(QRectF(0, S - 104, S, 46), Qt.AlignHCenter | Qt.AlignVCenter,
           "ASELI NGAWI")
p.end()

pm.save(OUT_PNG)

# ---------- ICO multi-size ----------
from PIL import Image
img = Image.open(OUT_PNG).convert("RGBA")
sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
         (128, 128), (256, 256)]
img.save(OUT_ICO, format="ICO", sizes=sizes)
print("ikon tersimpan:", OUT_PNG, flush=True)
print("ico tersimpan :", OUT_ICO, os.path.getsize(OUT_ICO), "bytes", flush=True)
