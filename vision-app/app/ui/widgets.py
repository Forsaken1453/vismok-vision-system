"""Widget visual khusus Leviathan."""
import math
import os
import random
import time

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (QImage, QPixmap, QPainter, QPen, QColor,
                           QLinearGradient, QFont, QBrush, QPainterPath)
from PySide6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout,
                               QGridLayout, QFrame, QProgressBar)

from app.ui.theme import ACCENT, ACCENT_2, BAD, GOOD, MUTED, PANEL_2, TEXT, TEXT_DIM, glow


class NeuralBackground(QWidget):
    """Animasi latar 'neural network': node + koneksi bergerak lambat."""

    def __init__(self, parent=None, density=26):
        super().__init__(parent)
        random.seed(42)
        self._nodes = []
        for i in range(density):
            self._nodes.append({
                "x": random.random(), "y": random.random(),
                "vx": (random.random() - 0.5) * 0.005,
                "vy": (random.random() - 0.5) * 0.005,
                "pulse": random.random(),
            })
        self._t = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def _tick(self):
        for n in self._nodes:
            n["x"] = (n["x"] + n["vx"]) % 1.0
            n["y"] = (n["y"] + n["vy"]) % 1.0
        self._t += 0.05
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # galaksi gradient dasar
        grad = QLinearGradient(QPointF(0, 0), QPointF(w, h))
        grad.setColorAt(0.0, QColor("#060A13"))
        grad.setColorAt(0.5, QColor("#091124"))
        grad.setColorAt(1.0, QColor("#050810"))
        p.fillRect(self.rect(), grad)

        # koneksi antar node (jarak < 25% lebar)
        pts = [(x * w, y * h) for x, y, *_ in
               [(n["x"], n["y"]) for n in self._nodes]]
        maxd = max(w, h) * 0.24
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
                if d < maxd:
                    a = int(60 * (1 - d / maxd))
                    p.setPen(QPen(QColor(34, 211, 238, a), 1))
                    p.drawLine(int(pts[i][0]), int(pts[i][1]),
                               int(pts[j][0]), int(pts[j][1]))

        # node berdenyut
        for k, n in enumerate(self._nodes):
            s = 2.4 + 1.6 * (0.5 + 0.5 * math.sin(self._t * 1.4 + n["pulse"] * 6.28))
            x, y = pts[k]
            p.setPen(QPen(QColor(56, 189, 248, 140), 1))
            p.setBrush(QColor(34, 211, 238, 70))
            p.drawEllipse(QPointF(x, y), s, s)
        p.end()


class HexLock(QWidget):
    """Ornamen hexagon glow untuk dekorasi header."""

    def __init__(self, size=26, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = min(w, h) / 2 - 2
        cx, cy = w / 2, h / 2
        poly = [QPointF(cx + r * math.cos(math.radians(60 * i - 30)),
                        cy + r * math.sin(math.radians(60 * i - 30)))
                for i in range(6)]
        p.setPen(QPen(QColor(ACCENT), 1.6))
        p.setBrush(QColor(34, 211, 238, 28))
        path = QPainterPath(poly[0])
        for pt in poly[1:]:
            path.lineTo(pt)
        path.closeSubpath()
        p.drawPath(path)
        p.end()


def cv2_to_pixmap(frame_bgr):
    """Konversi frame OpenCV (BGR) -> QPixmap."""
    if frame_bgr is None:
        return QPixmap()
    frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = frame.shape
    img = QImage(frame.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(img)


class CameraView(QWidget):
    """Tampilan kamera dengan overlay scan-line futuristik + box deteksi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.minimum = 16
        self._frame_pixmap = None
        self._scaled = None            # pre-scale utk ukuran widget (hemat CPU)
        self._scaled_key = None
        self._detections = []          # list dict {box, class_name, conf}
        self._scan_y = 0.0
        self._busy_zones = []          # [(t_start,)]
        self._t0 = time.time()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)          # ~25 fps animasi

    def set_frame(self, pixmap):
        if pixmap is None or pixmap.isNull():
            return
        self._frame_pixmap = pixmap
        self._scaled = None            # tanda: perlu pre-scale ulang
        self.update()

    def _get_scaled(self):
        if self._frame_pixmap is None or self._frame_pixmap.isNull():
            return None
        key = (self.width(), self.height())
        if self._scaled is None or self._scaled_key != key:
            # KeepAspectRatioByExpanding + crop offset disimpan utk mapping box
            pm = self._frame_pixmap
            self._scaled = pm.scaled(self.width(), self.height(),
                                     Qt.KeepAspectRatioByExpanding,
                                     Qt.SmoothTransformation)
            self._scaled_key = key
        return self._scaled

    def set_detections(self, dets):
        self._detections = dets or []
        self.update()

    def clear(self):
        """Buang frame & deteksi lama (dipakai saat kamera dilepas/retry)."""
        self._frame_pixmap = None
        self._scaled = None
        self._detections = []
        self.update()

    def _tick(self):
        self._scan_y = (time.time() - self._t0) % 2.2 / 2.2   # loop 2.2 dtk
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()

        # background
        p.fillRect(self.rect(), QColor("#050B14"))

        spm = self._get_scaled()
        if spm is not None:
            x = (w - spm.width()) // 2
            y = (h - spm.height()) // 2
            off_x, off_y = x, y
            p.drawPixmap(x, y, spm)
            # overlay gelap tipis utk visibilitas teks
            p.fillRect(0, 0, w, h, QColor(5, 11, 20, 45))
        else:
            p.fillRect(self.rect(), QColor("#050B14"))
            self._draw_grid(p, w, h)
            off_x, off_y = 0, 0

        # ---- gambar box hasil deteksi (HANYA saat ada frame) ----
        if spm is not None and self._frame_pixmap is not None:
            fw = self._frame_pixmap.width() or 1
            fh = self._frame_pixmap.height() or 1
            sx, sy = spm.width() / fw, spm.height() / fh
            for d in self._detections:
                self._draw_det_box(p, d, off_x, off_y, sx, sy)
            # ---- scan line (hanya saat kamera hidup)
            self._draw_scanline(p, w, h)
        else:
            # tanpa sinyal: tampilan tenang statis + pesan (anti glitch)
            f = self.font()
            f.setPointSize(11)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(34, 211, 238, 150))
            p.drawText(QRectF(0, h / 2 - 34, w, 26),
                       Qt.AlignCenter, "KAMERA  TIDAK  TERHUBUNG")
            f.setBold(False)
            f.setPointSize(8)
            p.setFont(f)
            p.setPen(QColor(148, 178, 200, 120))
            p.drawText(QRectF(0, h / 2 - 2, w, 20),
                       Qt.AlignCenter, "menunggu koneksi…")

        # ---- corner brackets
        self._draw_corners(p, w, h)
        p.end()

    def _draw_grid(self, p, w, h):
        p.setPen(QPen(QColor(18, 50, 82, 120), 1))
        step = 48
        for x in range(0, w, step):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            p.drawLine(0, y, w, y)

    def _draw_scanline(self, p, w, h):
        y = int(self._scan_y * h)
        grad = QLinearGradient(QPointF(0, y - 80), QPointF(0, y + 14))
        grad.setColorAt(0.0, QColor(34, 211, 238, 0))
        grad.setColorAt(0.9, QColor(34, 211, 238, 46))
        grad.setColorAt(1.0, QColor(34, 211, 238, 0))
        p.fillRect(0, max(0, y - 80), w, 94, grad)
        p.setPen(QPen(QColor(34, 211, 238, 200), 2))
        p.drawLine(0, y, w, y)

    def _draw_corners(self, p, w, h):
        p.setPen(QPen(QColor(34, 211, 238, 190), 3))
        m, ln = 26, 56          # margin & length
        # HANYA 2 sudut BAWAH — sudut atas bertabrakan dengan chip HUD
        # (MODEL / FPS / KAMERA) dan logo VISMOK, terlihat berantakan
        p.drawLine(m, h - m - ln, m, h - m)
        p.drawLine(m, h - m, m + ln, h - m)
        p.drawLine(w - m - ln, h - m, w - m, h - m)
        p.drawLine(w - m, h - m - ln, w - m, h - m)

    def _draw_det_box(self, p, d, off_x, off_y, sx=1.0, sy=1.0):
        from app.ui.fonts import FAMILY
        x1, y1, x2, y2 = d["box"]
        x1, y1 = int(x1 * sx + off_x), int(y1 * sy + off_y)
        x2, y2 = int(x2 * sx + off_x), int(y2 * sy + off_y)
        conf = d.get("conf", 0)
        color = QColor(ACCENT) if conf >= 0.75 else (
            QColor("#FBBF24") if conf >= 0.6 else QColor(BAD))
        w_box, h_box = x2 - x1, y2 - y1

        # outline tipis putus-putus (halus)
        dash = QPen(QColor(color.red(), color.green(), color.blue(), 90), 1)
        dash.setStyle(Qt.DashLine)
        p.setPen(dash)
        p.setBrush(Qt.NoBrush)
        p.drawRect(x1, y1, w_box, h_box)

        # bracket sudut tebal — gaya targeting HUD
        L = max(12, min(22, w_box // 4, h_box // 4))
        p.setPen(QPen(color, 3))
        p.drawLine(x1, y1, x1 + L, y1)
        p.drawLine(x1, y1, x1, y1 + L)
        p.drawLine(x2 - L, y1, x2, y1)
        p.drawLine(x2, y1, x2, y1 + L)
        p.drawLine(x1, y2 - L, x1, y2)
        p.drawLine(x1, y2, x1 + L, y2)
        p.drawLine(x2 - L, y2, x2, y2)
        p.drawLine(x2, y2 - L, x2, y2)

        # titik tengah
        cx, cy = x1 + w_box // 2, y1 + h_box // 2
        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 150), 1))
        p.drawLine(cx - 8, cy, cx - 3, cy)
        p.drawLine(cx + 3, cy, cx + 8, cy)
        p.drawLine(cx, cy - 8, cx, cy - 3)
        p.drawLine(cx, cy + 3, cx, cy + 8)

        # label
        label = f"{d['class_name'].upper()}  {conf:.0%}"
        f = QFont(FAMILY.get("display", "Rajdhani"))
        f.setPointSizeF(11.5)
        f.setBold(True)
        p.setFont(f)
        fm = p.fontMetrics()
        lw = fm.horizontalAdvance(label) + 22
        ly = y1 - 28 if y1 - 28 > 0 else y2 + 4
        # glow plate
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 235))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(x1 - 2, ly, lw, 24, 4, 4)
        p.setPen(QPen(QColor("#04131F"), 1))
        p.drawText(x1 + 9, ly + 17, label)


class StatChip(QLabel):
    """Chip status kecil di pojok layar — gaya HUD Orbitron."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._base = f"""
            background: rgba(5,11,20,0.82);
            border: 1px solid #123252;
            border-radius: 8px;
            padding: 5px 11px;
            font-family: "Orbitron";
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 1px;
            color: {TEXT_DIM};
        """
        self.setStyleSheet(self._base)

    def set_ok(self, ok=True, text=""):
        color = GOOD if ok else BAD
        self.setStyleSheet(self._base + f"color: {color}; border-color:{color};")
        if text:
            self.setText(text)


class SpeciesCard(QFrame):
    """Kartu rekomendasi pakan futuristik."""

    def __init__(self, rank, data, parent=None, on_detail=None):
        super().__init__(parent)
        self.data = data
        self.setObjectName("Card" if rank != 1 else "CardEmph")
        self.setMinimumHeight(168)
        self.setStyleSheet(self._style(rank))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)

        head = QHBoxLayout()
        badge = QLabel(f"#{rank}")
        badge.setStyleSheet(f"color:{ACCENT_2}; font-weight:800; font-size:15px;")
        nama = QLabel(str(data["nama"]))
        nama.setStyleSheet("font-size:17px; font-weight:700;")
        head.addWidget(badge)
        head.addWidget(nama)
        head.addStretch()
        if data.get("stok"):
            stash = QLabel("✔ STOK ADA" if int(data["stok"]) > 0 else "✖ KOSONG")
            stash.setStyleSheet("font-size:11px; font-weight:700; color:%s;"
                                % (GOOD if int(data["stok"]) > 0 else BAD))
            head.addWidget(stash)
        lay.addLayout(head)

        info = QHBoxLayout()
        info.setSpacing(18)
        for k, v, unit in [("SIFAT", data.get("bentuk", "-"), None),
                           ("UKURAN", data.get("ukuran", "-") or "-", None),
                           ("PROTEIN", data.get("protein", 0), "%")]:
            box = QVBoxLayout()
            lab = QLabel(k)
            lab.setStyleSheet("font-size:9px; color:%s; letter-spacing:2px;" % MUTED)
            val = QLabel(f"{v}{unit if unit else ''}")
            val.setStyleSheet("font-size:14px; font-weight:700;")
            box.addWidget(lab)
            box.addWidget(val)
            info.addLayout(box)
        info.addStretch()
        lay.addLayout(info)

        freq = data.get("frekuensi", "")
        if freq:
            f2 = QLabel(f"🕐 {freq}   •   {data.get('dosis','')}")
            f2.setStyleSheet(f"font-size:12px; color:{TEXT_DIM};")
            lay.addWidget(f2)

        bottom = QHBoxLayout()
        harga = QLabel("Rp {:,.0f}".format(float(data.get("harga", 0))).replace(",", "."))
        harga.setStyleSheet(f"font-size:18px; font-weight:800; color:{ACCENT};")
        bottom.addWidget(harga)
        bottom.addStretch()
        if on_detail is not None:
            btn = QFrame()
            from PySide6.QtWidgets import QPushButton
            bp = QPushButton("DETAIL ▸")
            bp.setStyleSheet("background: rgba(34,211,238,0.10); color:%s;"
                             "border:1px solid %s; border-radius:8px; "
                             "padding:4px 12px; font-size:11px; font-weight:700;" % (ACCENT, ACCENT))
            bp.setCursor(Qt.PointingHandCursor)
            bp.clicked.connect(lambda *a: on_detail(data))
            bottom.addWidget(bp)
        lay.addLayout(bottom)

        glow(self, ACCENT if rank == 1 else "#123252", blur=34 if rank == 1 else 10, parent=self)

    def _style(self, rank):
        border = ACCENT if rank == 1 else "#123252"
        return f"""
            QFrame {{
                background: rgba(13,31,51,0.92);
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """


class ConfBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConfBar")
        self.setRange(0, 100)
        self.setTextVisible(True)


class ValueGrid(QWidget):
    """Grid key-value kecil untuk detail ikan."""

    def __init__(self, items, parent=None):
        super().__init__(parent)
        lay = self._grid = QGridLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(14)
        for i, (k, v) in enumerate(items):
            lab = QLabel(k)
            lab.setStyleSheet(f"font-size:10px; color:{MUTED}; letter-spacing:2px;")
            val = QLabel(v or "-")
            val.setStyleSheet(f"font-size:15px; font-weight:600; color:{TEXT};")
            val.setWordWrap(True)
            lay.addWidget(lab, (i // 2) * 2, i % 2)
            lay.addWidget(val, (i // 2) * 2 + 1, i % 2)
        lay.setColumnStretch(2, 1)


class PlaceholderIcon(QLabel):
    """Ikon placeholder jenis ikan (emoji besar dalam lingkaran glow)."""

    def __init__(self, emoji="🐟", size=64, parent=None):
        super().__init__(emoji, parent)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            font-size:{int(size*0.5)}px;
            background: rgba(34,211,238,0.08);
            border: 1px solid {ACCENT_2};
            border-radius: {size//2}px;
        """)
        glow(self, ACCENT_2, 18, parent=self)


# ------------------------------------------------------------------
# Foto referensi (ikan / produk) dari assets/img
# ------------------------------------------------------------------
def _img_dir(subdir):
    try:
        from app.config import BASE_DIR
        return os.path.join(str(BASE_DIR), "assets", "img", subdir)
    except Exception:
        return os.path.join("assets", "img", subdir)


def photo_path(key, subdir="fish"):
    """Path foto referensi jika ada, else None."""
    if not key:
        return None
    p = os.path.join(_img_dir(subdir), f"{key}.jpg")
    return p if os.path.isfile(p) else None


def photo_pixmap(key, subdir="fish", w=0, h=0):
    """QPixmap foto referensi (opsional di-scale), atau None."""
    p = photo_path(key, subdir)
    if not p:
        return None
    pm = QPixmap(p)
    if pm.isNull():
        return None
    if w and h:
        pm = pm.scaled(w, h, Qt.KeepAspectRatioByExpanding,
                       Qt.SmoothTransformation)
    return pm


class PhotoImage(QLabel):
    """Foto referensi dalam kartu rounded; fallback emoji bila tidak ada."""

    def __init__(self, key, subdir="fish", emoji="🐟", size=84,
                 parent=None, radius=None, fit="cover"):
        super().__init__(parent)
        self._key = key
        self._subdir = subdir
        self._emoji = emoji
        self._size = size
        self._fit = fit
        self._radius = size // 2 if radius is None else radius
        self.setFixedSize(size, size)
        self._pm = photo_pixmap(key, subdir)
        if self._pm is None:
            # fallback: gaya PlaceholderIcon
            self.setAlignment(Qt.AlignCenter)
            self.setText(emoji)
            self.setStyleSheet(f"""
                font-size:{int(size*0.5)}px;
                background: rgba(34,211,238,0.08);
                border: 1px solid {ACCENT_2};
                border-radius: {self._radius}px;
            """)

    def refresh(self, key=None, emoji=None):
        """Ganti foto/emoji pada widget yang sama (tanpa buang-buat widget)."""
        if key is not None:
            self._key = key
        if emoji is not None:
            self._emoji = emoji
        self._pm = photo_pixmap(self._key, self._subdir)
        if self._pm is None:
            self.setAlignment(Qt.AlignCenter)
            self.setText(self._emoji)
        else:
            self.setText("")
            self.setStyleSheet("")
        self.update()

    def paintEvent(self, ev):
        if self._pm is None:
            super().paintEvent(ev)
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(0.5, 0.5, self._size - 1, self._size - 1)
        path = QPainterPath()
        path.addRoundedRect(r, self._radius, self._radius)
        p.setClipPath(path)
        if self._fit == "contain":
            # seluruh ikan terlihat (fit di dalam kotak)
            s = min(self._size / self._pm.width(), self._size / self._pm.height())
        else:
            s = max(self._size / self._pm.width(), self._size / self._pm.height())
        w, h = self._pm.width() * s, self._pm.height() * s
        x, y = (self._size - w) / 2, (self._size - h) / 2
        p.drawPixmap(QRectF(x, y, w, h), self._pm,
                     QRectF(0, 0, self._pm.width(), self._pm.height()))
        p.setClipping(False)
        p.setPen(QPen(QColor(ACCENT_2), 1))
        p.drawRoundedRect(r, self._radius, self._radius)
        p.end()
