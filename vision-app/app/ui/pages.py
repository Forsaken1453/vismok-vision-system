"""Halaman-halaman UI Leviathan.

Standby → Hasil Deteksi → Detail → Manual → Admin
"""
import os

from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QFrame, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox,
                               QComboBox, QTableWidget, QTableWidgetItem, QTabWidget,
                               QGridLayout as Grid, QScrollArea, QStackedLayout,
                               QSizePolicy, QButtonGroup)

from app.config import SNAP_DIR
from app.core import database as db
from app.ui import theme
from app.ui.theme import (ACCENT, ACCENT_2, BAD, GOOD, MUTED, PANEL_2, TEXT, TEXT_DIM, LINE, WARN)
from app.ui.widgets import (CameraView, ConfBar, HexLock, NeuralBackground,
                            PlaceholderIcon, PhotoImage, photo_pixmap,
                            SpeciesCard, StatChip, ValueGrid,
                            cv2_to_pixmap)
from PySide6.QtWidgets import QCheckBox


class QBtn(QPushButton):
    def __init__(self, text, primary=False, big=False, danger=False, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        if primary:
            self.setObjectName("Primary")
            theme.glow(self, ACCENT, 22, parent=self)
        elif danger:
            self.setObjectName("Danger")
        if big:
            self.setObjectName("Big")


# =====================================================================
# SIDEBAR NAVIGASI
# =====================================================================
NAV_ITEMS = [
    ("kamera",   "◉  KAMERA LIVE"),
    ("history",  "⧉  HASIL & RIWAYAT"),
    ("library",  "🐟  PANDUAN IKAN"),
    ("catalog",  "🧺  KATALOG PAKAN"),
    ("admin",    "⚙  ADMIN"),
]


def _make_back_bar(heading, on_back):
    bar = QWidget()
    lay = QHBoxLayout(bar)
    lay.setContentsMargins(24, 14, 24, 6)
    t = QLabel(heading)
    t.setObjectName("SectionH")
    lay.addWidget(t)
    lay.addStretch()
    b = QBtn("◀  KEMBALI")
    b.clicked.connect(on_back)
    lay.addWidget(b)
    return bar


class Sidebar(QFrame):
    """Rail navigasi kiri — menu utama Leviathan."""
    nav = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 20, 14, 16)
        outer.setSpacing(6)

        # logo block
        head = QVBoxLayout()
        head.setSpacing(2)
        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        bar = QFrame()
        bar.setFixedSize(4, 26)
        bar.setStyleSheet(f"background: {ACCENT}; border-radius: 2px;"
                          "border: none;")
        logo_row.addWidget(bar)
        logo_col = QVBoxLayout()
        logo_col.setSpacing(0)
        logo = QLabel("VISMOK")
        logo.setStyleSheet(f"font-family:'{theme.DISPLAY_FONT}';"
                           "font-size:15px; font-weight:800;"
                           "letter-spacing:3px; color:#EAF6FF;"
                           "background: transparent; border: none;")
        logo_col.addWidget(logo)
        logo_row.addLayout(logo_col)
        head.addLayout(logo_row)
        sub = QLabel("ASELI NGAWI  •  FISH VISION")
        sub.setStyleSheet(f"font-size:9px; color:{MUTED}; letter-spacing:2px;"
                          "background: transparent; border: none;")
        head.addWidget(sub)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {LINE}; border: none;")
        head.addWidget(line)
        outer.addLayout(head)
        outer.addSpacing(12)

        self.btns = {}
        self._grp = QButtonGroup(self)
        self._grp.setExclusive(True)
        for key, label in NAV_ITEMS:
            b = QPushButton(label)
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.nav.emit(k))
            self._grp.addButton(b)
            self.btns[key] = b
            outer.addWidget(b)
        outer.addStretch()

        # clock + tombol window + versi
        foot = QVBoxLayout()
        foot.setSpacing(6)

        ctr = QHBoxLayout()
        ctr.setSpacing(6)
        for label, cb in (("\u2013", self._win_min),
                          ("\u25a1", self._win_max),
                          ("\u2715", self._win_close)):
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedSize(52, 30)
            b.clicked.connect(cb)
            danger = (label == "\u2715")
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {PANEL_2};
                    border: 1px solid {LINE};
                    border-radius: 8px;
                    font-size: 13px;
                    color: {TEXT_DIM};
                }}
                QPushButton:hover {{ color: {BAD if danger else ACCENT};
                                     border-color: {BAD if danger else ACCENT}; }}
            """)
            ctr.addWidget(b)
        foot.addLayout(ctr)

        self.clock = QLabel("")
        self.clock.setObjectName("Clock")
        foot.addWidget(self.clock)
        ver = QLabel("VISMOK v2.1 • PAMERAN 2026")
        ver.setStyleSheet(f"font-size:10px; color:{MUTED};")
        foot.addWidget(ver)
        outer.addLayout(foot)

        self.set_active("kamera")
        self._ct = QTimer(self)
        self._ct.timeout.connect(self._tick_clock)
        self._ct.start(1000)
        self._tick_clock()

    def _tick_clock(self):
        import datetime
        now = datetime.datetime.now()
        self.clock.setText(now.strftime("%H:%M:%S %p   ").replace(" %p", "") + "LIVE")

    # --- kontrol jendela ---
    def _win_min(self):
        self.window().showMinimized()

    def _win_max(self):
        w = self.window()
        if w.isFullScreen() or w.isMaximized():
            w.showNormal()
        else:
            w.showMaximized()

    def _win_close(self):
        self.window().close()

    def set_active(self, key):
        b = self.btns.get(key)
        if b is not None:
            b.setChecked(True)



class QBtn(QPushButton):
    def __init__(self, text, primary=False, big=False, danger=False, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        if primary:
            self.setObjectName("Primary")
            theme.glow(self, ACCENT, 22, parent=self)
        elif danger:
            self.setObjectName("Danger")
        if big:
            self.setObjectName("Big")


# =====================================================================
# 1. STANDBY
# =====================================================================
class StandbyPage(QWidget):
    species_detected = Signal(str, float, object)   # class_name, conf, frame_pixmap
    source_picked = Signal(str)                     # "webcam" | "droidcam" | "auto"
    camera_retry = Signal()
    mode_picked = Signal(str)                       # "auto" | "manual"
    manual_scan = Signal()
    droid_ip_request = Signal()                     # tombol "IP HP..."

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.camera = CameraView()
        lay.addWidget(self.camera)

        # --- lapisan HUD (overlay) ---
        self.hud = QWidget(self)
        hud_l = QVBoxLayout(self.hud)
        hud_l.setContentsMargins(0, 0, 0, 0)
        self.hud.setStyleSheet("background: transparent;")

        top = QHBoxLayout()
        top.setContentsMargins(24, 14, 20, 0)
        top.setSpacing(8)
        bar = QFrame()
        bar.setFixedSize(4, 24)
        bar.setStyleSheet(f"background: {ACCENT}; border-radius: 2px;"
                          "border: none;")
        top.addWidget(bar)
        logo = QLabel("VISMOK")
        logo.setObjectName("Title")
        logo.setStyleSheet("font-size:19px; letter-spacing:4px; color:#EAF6FF;"
                           "background: transparent; border: none;")
        top.addWidget(logo)
        sub = QLabel("ASELI NGAWI")
        sub.setStyleSheet("font-size:10px; letter-spacing:3px; color:#7FB6D9;"
                          "background: transparent; border: none;"
                          "padding-top:7px;")
        top.addWidget(sub)
        top.addStretch()
        self.chip_cam = StatChip("KAMERA: —")
        self.chip_model = StatChip("MODEL: —")
        self.chip_fps = StatChip("FPS: —")
        self.chip_status = StatChip("● SCANNING")
        self.chip_status.setStyleSheet("color:%s; border-color:%s;" % (GOOD, GOOD))
        for c in (self.chip_status, self.chip_model, self.chip_fps, self.chip_cam):
            top.addWidget(c)
        hud_l.addLayout(top)
        hud_l.addStretch()

        # hint arahan: baris SENDIRI di atas bar kontrol (tidak digencet
        # tombol kamera/mode - sebelumnya teks terpotong "SCAN OTOMA…")
        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(28, 0, 28, 10)
        self.hint = QLabel("◉  ARAHKAN  IKAN  KE  KAMERA  —  SCAN  OTOMATIS")
        self.hint.setObjectName("Hint")
        self.hint.setStyleSheet(
            f"font-family:{theme.DISPLAY_FONT}; font-size:12px;"
            "letter-spacing:2px; color:#7FB6D9;"
            "background: transparent; border: none;")
        hint_row.addWidget(self.hint)
        hint_row.addStretch()
        hud_l.addLayout(hint_row)

        bottom = QWidget()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(28, 0, 28, 26)

        # --- switch sumber kamera: LAPTOP / HP (DroidCam) / AUTO ---
        src_lbl = QLabel("KAMERA  ▸")
        src_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;"
                              "letter-spacing:2px; padding-right:6px;")
        bl.addWidget(src_lbl)
        self.src_btns = {}
        self._src_grp = QButtonGroup(self)
        self._src_grp.setExclusive(True)
        for key, label in (("webcam", "LAPTOP"), ("droidcam", "HP (DROIDCAM)"),
                           ("auto", "AUTO")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("Src", key)
            b.setStyleSheet("""
                QPushButton {
                    background: rgba(5,11,20,0.82);
                    border: 1px solid #123252;
                    border-radius: 8px;
                    padding: 7px 13px;
                    font-family: "Orbitron";
                    font-size: 10px;
                    font-weight: 600;
                    letter-spacing: 1px;
                    color: #9DB2C7;
                }
                QPushButton:checked {
                    color: #22D3EE;
                    border-color: #22D3EE;
                    background: rgba(34,211,238,0.10);
                }
                QPushButton:hover { color: #E6F0FA; }
            """)
            b.clicked.connect(lambda _=False, k=key: self.source_picked.emit(k))
            self._src_grp.addButton(b)
            self.src_btns[key] = b
            bl.addWidget(b)
        self.set_source_active("webcam")

        # --- tombol IP HP: sambung DroidCam di lokasi/WiFi baru ---
        b_ip = QPushButton("IP  HP...")
        b_ip.setCursor(Qt.PointingHandCursor)
        b_ip.setToolTip("Sambung kamera HP (DroidCam) lewat alamat IP WiFi")
        b_ip.setStyleSheet("""
            QPushButton {
                background: rgba(34,211,238,0.08);
                border: 1px dashed #22D3EE;
                border-radius: 8px;
                padding: 7px 13px;
                font-family: "Orbitron";
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1px;
                color: #22D3EE;
            }
            QPushButton:hover { background: rgba(34,211,238,0.18); }
        """)
        b_ip.clicked.connect(self.droid_ip_request.emit)
        bl.addWidget(b_ip)

        # --- mode deteksi: AUTO (realtime) / MANUAL (tombol) ---
        mode_lbl = QLabel("MODE  ▸")
        mode_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;"
                               "letter-spacing:2px; padding-right:6px;")
        bl.addWidget(mode_lbl)
        self.mode_btns = {}
        self._mode_grp = QButtonGroup(self)
        self._mode_grp.setExclusive(True)
        for key, label in (("auto", "AUTO"), ("manual", "MANUAL")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background: rgba(5,11,20,0.82);
                    border: 1px solid #123252;
                    border-radius: 8px;
                    padding: 7px 13px;
                    font-family: "Orbitron";
                    font-size: 10px;
                    font-weight: 600;
                    letter-spacing: 1px;
                    color: #9DB2C7;
                }
                QPushButton:checked {
                    color: #34D399;
                    border-color: #34D399;
                    background: rgba(52,211,153,0.10);
                }
                QPushButton:hover { color: #E6F0FA; }
            """)
            b.clicked.connect(lambda _=False, k=key: self.mode_picked.emit(k))
            self._mode_grp.addButton(b)
            self.mode_btns[key] = b
            bl.addWidget(b)

        self.btn_manual_scan = QBtn("◎  DETEKSI MANUAL", big=True)
        self.btn_manual_scan.clicked.connect(self.manual_scan.emit)
        self.btn_manual_scan.setToolTip("Tangkap frame kamera sekarang, lalu deteksi")
        self.btn_manual_scan.hide()
        bl.addWidget(self.btn_manual_scan)

        btn_manual = QBtn("≡  PILIH JENIS IKAN", big=True)
        btn_manual.clicked.connect(lambda: self.window().go_page("manual"))
        bl.addWidget(btn_manual)
        hud_l.addWidget(bottom)
        hud_l.setAlignment(bottom, Qt.AlignBottom)
        self.set_mode_active("auto")

        # --- panel detail deteksi LIVE (mode glass samping kanan) ---
        self.det_panel = QFrame(self)
        self.det_panel.setObjectName("GlassSurf")
        self.det_panel.setFixedWidth(322)
        theme.glow(self.det_panel, ACCENT, 26, parent=self.det_panel)
        dp = QVBoxLayout(self.det_panel)
        dp.setContentsMargins(18, 16, 18, 14)
        dp.setSpacing(8)
        dt1 = QLabel("◉   LIVE   DETECTION")
        dt1.setStyleSheet(f"font-family:{theme.DISPLAY_FONT}; font-size:14px;"
                          f"color:{ACCENT}; letter-spacing:3px; font-weight:700;"
                          "background: transparent; border: none;")
        dp.addWidget(dt1)
        dp.addWidget(self._hairline())
        self.det_rows = QVBoxLayout()
        self.det_rows.setSpacing(8)
        dp.addLayout(self.det_rows)
        dp.addStretch()
        dp.addWidget(self._hairline())
        meta = QLabel("")
        meta.setObjectName("Small")
        meta.setWordWrap(True)
        meta.setStyleSheet(f"color:{MUTED}; font-size:11px; letter-spacing:1px;"
                           "background: transparent; border: none;")
        self.det_meta = meta
        dp.addWidget(meta)
        self._det_sig = None
        self._update_rows_placeholder()
        self._build_offline()

        # pulse animasi "MENYAPU..." saat tidak ada deteksi
        self._scan_n = 0
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._pulse_scan)
        self._scan_timer.start(600)

    def set_source_active(self, key):
        b = self.src_btns.get(key)
        if b is not None:
            b.setChecked(True)

    def set_mode_active(self, key):
        for k, b in self.mode_btns.items():
            b.setChecked(k == key)
        manual = (key == "manual")
        self.btn_manual_scan.setVisible(manual)
        self.hint.setVisible(not manual)
        if manual:
            self.chip_status.setText("● MANUAL  SIAP")
            self.chip_status.setStyleSheet(
                "color:%s; border-color:%s;" % (GOOD, GOOD))
        else:
            self.chip_status.setText("● SCANNING")
            self.chip_status.setStyleSheet(
                "color:%s; border-color:%s;" % (GOOD, GOOD))
            self.hint.setText(
                "◉  ARAHKAN  IKAN  KE  KAMERA  —  SCAN  OTOMATIS")

    @staticmethod
    def _hairline():
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background-color:{LINE}; color:{LINE}; max-height:1px;")
        return line

    def _update_rows_placeholder(self):
        while self.det_rows.count():
            it = self.det_rows.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        ph = QLabel("   ◉ MENYAPU...")
        ph.setStyleSheet(f"color:{MUTED}; font-size:12px;"
                         "background: transparent; border: none;")
        self._ph_lbl = ph
        self.det_rows.addWidget(ph)
        self.det_meta.setText("MODEL  :  —\nTHRESH :  —\nFPS    :  —")

    def _pulse_scan(self):
        """Animasi kecil saat scan: titik-titik + warna chip berdenyut."""
        self._scan_n = (self._scan_n + 1) % 3
        if getattr(self, "_det_sig", ()) in (None, ()):
            ph = getattr(self, "_ph_lbl", None)
            if ph is not None:
                try:
                    if ph.isVisible():
                        ph.setText("   ◉ MENYAPU" + "." * (self._scan_n + 1))
                except RuntimeError:
                    self._ph_lbl = None

    def update_hud(self, dets, fps=None, model="—", threshold="—", snaps=None):
        """Update panel deteksi live — dipanggil dari loop utama (throttled)."""
        sig = tuple((d["class_name"], round(d["conf"], 2)) for d in (dets or []))
        if sig == self._det_sig:
            if fps is not None:
                m = f"MODEL  :  {model}\nTHRESH :  {threshold}\nFPS    :  {fps}"
                if self.det_meta.text() != m:
                    self.det_meta.setText(m)
            return
        self._det_sig = sig
        while self.det_rows.count():
            it = self.det_rows.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        if not dets:
            ph = QLabel("   ◉ MENYAPU...")
            ph.setStyleSheet(f"color:{MUTED}; font-size:12px;"
                             "background: transparent; border: none;")
            self._ph_lbl = ph
            self.det_rows.addWidget(ph)
        else:
            for k, d in enumerate(sorted(dets, key=lambda x: -x["conf"])[:4], 1):
                row = QFrame()
                # setObjectName("Card") atau karte kecil bar-bar ini
                row.setStyleSheet("""
                    QFrame {
                        background: rgba(4,16,28,0.82);
                        border: 1px solid rgba(34,211,238,0.28);
                        border-radius: 9px;
                    }
                    QLabel { border: none; background: transparent; }
                """)
                row.setFixedHeight(56)
                rl = QHBoxLayout(row)
                rl.setContentsMargins(12, 8, 12, 8)
                rl.setSpacing(10)
                num = QLabel(f"#{k}")
                num.setStyleSheet(f"color:{ACCENT_2}; font-weight:800;"
                                  f"font-family:{theme.DISPLAY_FONT}; font-size:14px;")
                rl.addWidget(num)
                col = QVBoxLayout()
                nm = QLabel(str(d["class_name"]).upper())
                nm.setStyleSheet(f"font-family:{theme.DISPLAY_FONT}; font-size:16px;"
                                 f"font-weight:700; letter-spacing:1px;")
                cf = QLabel(f"kepercayaan {d['conf']:.0%}")
                cf.setStyleSheet(f"font-size:10px; color:{TEXT_DIM};")
                col.addWidget(nm)
                col.addWidget(cf)
                rl.addLayout(col, 10)
                pc = float(d["conf"])
                color = GOOD if pc >= 0.75 else (WARN if pc >= 0.6 else BAD)
                val = QLabel(f"{pc:.0%}")
                val.setStyleSheet(f"color:{color}; font-weight:800;"
                                  f"font-family:{theme.DISPLAY_FONT}; font-size:17px;")
                rl.addWidget(val)
                self.det_rows.addWidget(row)
        m = f"MODEL  :  {model}\nTHRESH :  {threshold}\nFPS    :  {fps if fps else '—'}"
        self.det_meta.setText(m)

    def _build_offline(self):
        # --- overlay KAMERA OFFLINE ---
        self.offline = QFrame(self)
        self.offline.setStyleSheet("""
            QFrame {
                background: rgba(5,11,20,0.88);
                border: 1px solid rgba(248,113,113,0.6);
                border-radius: 16px;
            }
            QLabel { border: none; background: transparent; }
        """)
        ol = QVBoxLayout(self.offline)
        ol.setContentsMargins(30, 24, 30, 24)
        ol.setSpacing(12)
        ol.setAlignment(Qt.AlignCenter)
        t1 = QLabel("⚠   K A M E R A   O F F L I N E")
        t1.setStyleSheet(f"font-family:{theme.DISPLAY_FONT}; font-size:26px;"
                         f"font-weight:800; color:{BAD}; letter-spacing:2px;")
        t1.setAlignment(Qt.AlignCenter)
        ol.addWidget(t1)
        self.offline_detail = QLabel("")
        self.offline_detail.setWordWrap(True)
        self.offline_detail.setStyleSheet(f"color:{TEXT_DIM}; font-size:13px;")
        self.offline_detail.setAlignment(Qt.AlignCenter)
        ol.addWidget(self.offline_detail)
        tips = QLabel("Checklist cepat:\n"
                      "  1. Windows Settings ▸ Privacy & Security ▸ Camera ▸ "
                      "aktifkan 'Let desktop apps access your camera'\n"
                      "  2. Pastikan webcam fisik tidak tertutup / dimatikan (tombol Fn F9)\n"
                      "  3. Untuk DroidCam: app DroidCam harus jalan di HP & "
                      "satu WiFi dengan laptop")
        tips.setWordWrap(True)
        tips.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
        ol.addWidget(tips)
        row = QHBoxLayout()
        row.addStretch()
        b_retry = QBtn("↻   COBA LAGI", primary=True, big=True)
        b_retry.clicked.connect(self.camera_retry)
        row.addWidget(b_retry)
        b_cfg = QBtn("⚙   ATUR KAMERA", big=True)
        b_cfg.clicked.connect(lambda: self.window().go_page("admin"))
        row.addWidget(b_cfg)
        row.addStretch()
        ol.addLayout(row)
        self.offline.hide()

    def show_camera_offline(self, show=True, detail=""):
        self.offline_detail.setText(detail or "")
        self.offline.setVisible(show)
        if show:
            self.offline.setGeometry(self.rect())

    def update_hud_meta(self, model="—", threshold="—", fps=None):
        """Ganti meta panel tanpa mengubah baris deteksi."""
        m = f"MODEL  :  {model}\nTHRESH :  {threshold}\nFPS    :  {fps if fps else '—'}"
        if self.det_meta.text() != m:
            self.det_meta.setText(m)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.hud.setGeometry(self.rect())
        if self.offline.isVisible():
            self.offline.setGeometry(self.rect())
        # panel deteksi live: kanan-tengah
        self.det_panel.setGeometry(
            self.rect().right() - self.det_panel.width() - 20,
            int(self.rect().height() * 0.18),
            self.det_panel.width(),
            min(460, self.rect().height() - int(self.rect().height() * 0.34)))


# =====================================================================
# 2. HASIL DETEKSI
# =====================================================================
class ResultPage(QWidget):
    species_detected = Signal(str, float, object)
    pdf_export = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._species = None
        self._recs = []

        rot = QVBoxLayout(self)
        rot.setContentsMargins(0, 0, 0, 0)
        rot.addWidget(_make_back_bar("HASIL  ANALISIS  VISUAL",
                                     lambda: self.window().go_page("standby")))
        body = QHBoxLayout()
        body.setContentsMargins(28, 6, 28, 24)
        body.setSpacing(24)

        # --- kiri : snapshot ---
        left = QVBoxLayout()
        left.setSpacing(10)
        self.snap = QLabel("🪞")
        self.snap.setFixedSize(440, 330)
        self.snap.setAlignment(Qt.AlignCenter)
        self.snap.setStyleSheet("""
            background: rgba(13,31,51,0.9);
            border: 1px solid #123252; border-radius: 14px; font-size: 60px;
        """)
        theme.glow(self.snap, ACCENT, 26, parent=self.snap)
        left.addWidget(self.snap)
        left.addStretch()

        self.conf_bar = ConfBar()
        self.conf_bar.setFormat("KEPERCAYAAN  %p%")
        self.conf_bar.setFixedHeight(26)
        left.addWidget(self.conf_bar)
        body.addLayout(left)

        # --- kanan : hasil ---
        right = QVBoxLayout()
        right.setSpacing(14)
        head = QHBoxLayout()
        self._head_lay = head
        self.icon = PhotoImage(None, emoji="🐟", size=66, fit="contain")
        head.addWidget(self.icon)
        txtcol = QVBoxLayout()
        self.kicker = QLabel("JENIS IKAN TERDETEKSI")
        self.kicker.setObjectName("SubTitle")
        self.name = QLabel("—")
        self.name.setObjectName("SpeciesName")
        theme.glow(self.name, ACCENT, 34, parent=self.name)
        txtcol.addWidget(self.kicker)
        txtcol.addWidget(self.name)
        head.addLayout(txtcol)
        head.addStretch()
        right.addLayout(head)

        sec = QLabel("⚖  REKOMENDASI  PAKAN  COCOK")
        sec.setObjectName("SectionH")
        right.addWidget(sec)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        self.cards_holder = QWidget()
        self.cards_holder.setStyleSheet("background: transparent;")
        self.cards_lay = QVBoxLayout(self.cards_holder)
        self.cards_lay.setContentsMargins(0, 0, 12, 0)
        self.cards_lay.setSpacing(12)
        scroll.setWidget(self.cards_holder)
        right.addWidget(scroll, 10)

        foot = QHBoxLayout()
        b_detail = QBtn("◉  DETAIL & TIPS", primary=True, big=True)
        b_detail.clicked.connect(self._go_detail)
        foot.addWidget(b_detail)
        b_pdf = QBtn("🖨  EXPORT PDF")
        b_pdf.setToolTip("Cetak kwitansi rekomendasi + tips perawatan")
        b_pdf.clicked.connect(self.pdf_export.emit)
        foot.addWidget(b_pdf)
        foot.addStretch()
        b_rescan = QBtn("🔄  SCAN ULANG")
        b_rescan.clicked.connect(lambda: self.window().go_page("standby"))
        foot.addWidget(b_rescan)
        b_manual = QBtn("≡  PILIH JENIS IKAN")
        b_manual.clicked.connect(lambda: self.window().go_page("manual"))
        foot.addWidget(b_manual)
        right.addLayout(foot)
        body.addLayout(right, 10)

        rot.addLayout(body)

    def _go_detail(self):
        if self._species:
            self.window().show_detail(self._species)

    def set_result(self, species, snapshot_pixmap, conf=None):
        self._species = species
        self.name.setText(f"{species.get('emoji','🐟')}  {species['display_name'].upper()}")
        # ganti foto pada ikon yang sama (fallback emoji bila tak ada foto)
        self.icon.refresh(species.get("class_name"),
                          species.get("emoji", "🐟"))
        if snapshot_pixmap is not None and not snapshot_pixmap.isNull():
            self.snap.setText("🪞")
            self.snap.setPixmap(snapshot_pixmap.scaled(
                self.snap.width(), self.snap.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            # tanpa snapshot → tampilkan foto referensi ikan
            pm = photo_pixmap(species.get("class_name"), "fish",
                              self.snap.width(), self.snap.height())
            if pm is not None:
                self.snap.setText("")
                self.snap.setPixmap(pm)
            else:
                self.snap.setPixmap(QPixmap())
                self.snap.setText("🪞")
        if conf is not None:
            self.conf_bar.setValue(int(conf * 100))
        self._load_recs(species["id"])

    def set_conf_bar(self, conf):
        self.conf_bar.setValue(int(conf * 100))

    def clear(self):
        self._species = None
        self.name.setText("—")
        self.conf_bar.setValue(0)
        self._clear_cards()

    def _clear_cards(self):
        while self.cards_lay.count():
            item = self.cards_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _load_recs(self, species_id):
        self._clear_cards()
        recs = db.recs_for_species(species_id)
        if not recs:
            empty = QLabel("Belum ada rekomendasi — tambahkan via ▷ ADMIN")
            empty.setStyleSheet(f"color:{MUTED}; font-size:13px; padding:10px;")
            self.cards_lay.addWidget(empty)
        for i, r in enumerate(recs, 1):
            self.cards_lay.addWidget(SpeciesCard(i, r, on_detail=self._open_tips_parent))
        self.cards_lay.addStretch()

    def _open_tips_parent(self, data):
        if self._species:
            self.window().show_detail(self._species)


# =====================================================================
# 3. DETAIL & TIPS
# =====================================================================
class DetailPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        rot = QVBoxLayout(self)
        rot.setContentsMargins(0, 0, 0, 0)
        rot.addWidget(_make_back_bar("DETAIL  IKAN  &  TIPS",
                                     lambda: self.window().go_page("result")))

        self.body = QScrollArea()
        self.body.setWidgetResizable(True)
        self.body.setFrameShape(QFrame.NoFrame)
        self.body.setStyleSheet("background: transparent;")
        self.holder = QWidget()
        self.holder.setStyleSheet("background: transparent;")
        self.lay = QVBoxLayout(self.holder)
        self.lay.setContentsMargins(30, 10, 30, 30)
        self.lay.setSpacing(18)
        self.body.setWidget(self.holder)
        rot.addWidget(self.body, 10)

    def set_species(self, sp):
        # clear
        while self.lay.count():
            it = self.lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        # header
        head = QWidget()
        head.setStyleSheet("""
            QFrame { background: rgba(13,31,51,0.92); border: 1px solid #123252;
                     border-radius: 16px; }
        """)
        head_l = QHBoxLayout(head)
        head_l.setContentsMargins(22, 18, 22, 18)
        icon = PhotoImage(sp.get("class_name"), size=88,
                          emoji=sp.get("emoji", "🐟"), fit="contain")
        head_l.addWidget(icon)
        tcol = QVBoxLayout()
        name = QLabel(f"{sp['display_name'].upper()}")
        name.setObjectName("SpeciesName")
        tcol.addWidget(name)
        desc = QLabel(sp.get("deskripsi", ""))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{TEXT_DIM}; font-size:13px;")
        tcol.addWidget(desc)
        head_l.addLayout(tcol)
        head_l.addStretch()
        self.lay.addWidget(head)

        # grid data
        grid_card = QFrame()
        grid_card.setObjectName("Card")
        grid_card.setStyleSheet("""
            QFrame#Card { background: rgba(13,31,51,0.92);
                          border: 1px solid #123252; border-radius: 14px; }
        """)
        gl = QVBoxLayout(grid_card)
        gl.setContentsMargins(8, 8, 8, 8)
        gl.addWidget(ValueGrid([
            ("HABITAT", sp.get("habitat")),
            ("SIFAT", sp.get("sifat")),
            ("SUHU IDEAL", sp.get("suhu")),
            ("pH IDEAL", sp.get("ph")),
            ("UKURAN DEWASA", sp.get("ukuran")),
            ("NAMA CLASS MODEL", sp.get("class_name")),
        ]))
        self.lay.addWidget(grid_card)

        # tips
        tips_card = QFrame()
        tips_card.setStyleSheet("QFrame { background: rgba(10,40,60,0.65);"
                                " border:1px solid rgba(34,211,238,0.35);"
                                " border-radius:14px; }")
        tl = QVBoxLayout(tips_card)
        tl.setContentsMargins(20, 16, 20, 16)
        tl.setSpacing(10)
        h = QLabel("⚡  TIPS  PERAWATAN")
        h.setObjectName("SectionH")
        tl.addWidget(h)
        for i, tip in enumerate(sp.get("tips") or [], 1):
            row = QLabel(f"◆   {tip}")
            row.setWordWrap(True)
            row.setStyleSheet(f"font-size:13px; color:{TEXT};")
            tl.addWidget(row)
        if not sp.get("tips"):
            tl.addWidget(QLabel("Belum ada tips."))
        self.lay.addWidget(tips_card)
        self.lay.addStretch()


# =====================================================================
# 4. PILIH MANUAL / PANDUAN IKAN
# =====================================================================
class ManualPage(QWidget):
    def __init__(self, parent=None, mode="result"):
        super().__init__(parent)
        self._mode = mode          # "result" → pilih utk scan; "detail" → panduan
        title = "PILIH  JENIS  IKAN  MANUAL" if mode == "result" \
            else "PANDUAN  IKAN  —  KLIK  UTK  LIHAT  DETAIL"
        back_to = "standby" if mode == "result" else "kamera"
        rot = QVBoxLayout(self)
        rot.setContentsMargins(0, 0, 0, 0)
        rot.addWidget(_make_back_bar(title, lambda: self.window().go_page(back_to)))
        note = ("Gunakan ini bila kamera tidak menemukan ikan, atau hasil deteksi "
                "kurang tepat.") if mode == "result" else \
               ("Referensi jenis ikan dengan rekomendasi pakan & tips perawatan "
                "akurat per jenis.")
        note = QLabel(note)
        note.setStyleSheet(f"color:{MUTED}; font-size:12px; padding: 0 28px;")
        rot.addWidget(note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        self.grid_holder = QWidget()
        self.grid_holder.setStyleSheet("background: transparent;")
        self.grid = Grid(self.grid_holder)
        self.grid.setContentsMargins(28, 10, 28, 28)
        self.grid.setSpacing(16)
        scroll.setWidget(self.grid_holder)
        rot.addWidget(scroll, 10)

        self._populate(None)

    def set_species_list(self, species):
        self._populate(species)

    def _populate(self, species):
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        species = species or db.species_all()
        for i, sp in enumerate(species):
            card = QFrame()
            card.setObjectName("Card")
            card.setStyleSheet("""
                QFrame { background: rgba(13,31,51,0.92);
                         border: 1px solid #123252; border-radius: 14px; }
                QFrame:hover { border-color: %s; }
            """ % ACCENT)
            card.setFixedSize(250, 236)
            card.setCursor(Qt.PointingHandCursor)
            vl = QVBoxLayout(card)
            vl.setContentsMargins(18, 16, 18, 14)
            vl.setSpacing(8)
            icon = PhotoImage(sp.get("class_name"),
                              emoji=sp.get("emoji", "🐟"), size=96,
                              radius=16, fit="contain")
            icon.setAlignment(Qt.AlignCenter)
            vl.addWidget(icon, 0, Qt.AlignHCenter)
            nm = QLabel(sp["display_name"])
            nm.setAlignment(Qt.AlignCenter)
            nm.setStyleSheet("font-size:16px; font-weight:700;")
            cl = QLabel(sp["class_name"])
            cl.setAlignment(Qt.AlignCenter)
            cl.setStyleSheet(f"font-size:10px; color:{MUTED};")
            vl.addWidget(nm)
            vl.addWidget(cl)
            card.mousePressEvent = (lambda s, species=sp: (
                lambda ev: self._open(species)))
            self.grid.addWidget(card, i // 4, i % 4)
        self.grid.setRowStretch(self.grid.rowCount(), 1)
        self.grid.setColumnStretch(5, 1)

    def _open(self, species):
        if self._mode == "detail":
            self.window().show_detail(species)
        else:
            self.window().select_manual(species)


# =====================================================================
# 4b. RIWAYAT DETEKSI (dari database)
# =====================================================================
class HistoryPage(QWidget):
    clear_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        rot = QVBoxLayout(self)
        rot.setContentsMargins(0, 0, 0, 0)
        rot.addWidget(_make_back_bar("HASIL  &  RIWAYAT  DETEKSI",
                                     lambda: self.window().go_page("kamera")))

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(28, 4, 28, 24)
        bl.setSpacing(10)

        self.stat_lbl = QLabel("")
        self.stat_lbl.setObjectName("SubTitle")
        bl.addWidget(self.stat_lbl)

        self.tbl = QTableWidget()
        self.tbl.setColumnCount(5)
        self.tbl.setHorizontalHeaderLabels(["WAKTU", "IKAN", "CLASS",
                                            "KEPERCAYAAN", "SNAPSHOT"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setColumnWidth(0, 190)
        self.tbl.setColumnWidth(1, 200)
        self.tbl.setColumnWidth(2, 140)
        self.tbl.setColumnWidth(3, 110)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.doubleClicked.connect(self._open_row)
        bl.addWidget(self.tbl, 10)

        bars = QHBoxLayout()
        b_re = QBtn("↻  REFRESH")
        b_re.clicked.connect(self.reload)
        bars.addWidget(b_re)
        b_del = QBtn("🗑  HAPUS RIWAYAT")
        b_del.clicked.connect(self._clear_history)
        bars.addWidget(b_del)
        bars.addStretch()
        tip = QLabel("klik 2x baris = buka detail jenis ikan ini")
        tip.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        bars.addWidget(tip)
        bl.addLayout(bars)

        rot.addWidget(body, 10)
        self.reload()

    def _clear_history(self):
        """Konfirmasi dulu, lalu kirim sinyal hapus semua riwayat."""
        from PySide6.QtWidgets import QMessageBox
        n = db.detections_count()
        if n == 0:
            QMessageBox.information(self, "HAPUS RIWAYAT",
                                    "Riwayat masih kosong - tidak ada yang dihapus.")
            return
        ret = QMessageBox.question(
            self, "HAPUS RIWAYAT",
            f"Hapus SEMUA riwayat deteksi ({n} baris) beserta snapshot-nya?\n"
            "Tindakan ini tidak bisa dibatalkan.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.clear_requested.emit()

    def reload(self):
        rows = db.detections_list()
        self.tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [r["ts"] or "-",
                    f"{r.get('emoji') or '🐟'}  {r.get('display_name') or r['class_name']}",
                    r["class_name"],
                    f"{r['conf']:.0%}",
                    r["snapshot"] or "-"]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 0:
                    it.setFont(QFont(theme.DISPLAY_FONT, 12))
                self.tbl.setItem(i, j, it)
        self.stat_lbl.setText(f"Total riwayat: {len(rows)} deteksi tersimpan • "
                              "snapshot ada di data/snapshots/")

    def _open_row(self, index):
        row = index.row()
        it = self.tbl.item(row, 2)
        if it is None:
            return
        sp = next((s for s in db.species_all() if s["class_name"] == it.text()), None)
        if sp:
            self.window().show_detail(sp)


# =====================================================================
# 4c. KATALOG PAKAN (view pembeli, read-only)
# =====================================================================
class CatalogPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rot = QVBoxLayout(self)
        self._rot.setContentsMargins(0, 0, 0, 0)
        self._rot.addWidget(_make_back_bar("KATALOG  PAKAN  TOKO",
                                           lambda: self.window().go_page("kamera")))
        self._body = None
        QTimer.singleShot(0, self.reload)

    def showEvent(self, ev):
        # rebuild saat halaman benar-benar tampil (body yg dibuat saat
        # halaman tersembunyi tidak pernah muncul - quirk layout)
        super().showEvent(ev)
        QTimer.singleShot(0, self.reload)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # re-grid debounced saat jendela di-resize (kolom adaptif)
        if not hasattr(self, "_rz_timer"):
            self._rz_timer = QTimer(self)
            self._rz_timer.setSingleShot(True)
            self._rz_timer.setInterval(350)
            self._rz_timer.timeout.connect(self._maybe_regrid)
        self._rz_timer.start()

    def _maybe_regrid(self):
        if self._body is None:
            return
        w_win = self.window().width() if self.window() else 1600
        cols = max(3, min(5, (w_win - 340) // 300)) if w_win > 800 else 2
        if cols != getattr(self, "_last_cols", None):
            self.reload()

    def reload(self):
        if self._body is not None:
            self._body.setParent(None)
            self._body.deleteLater()
        self._body = QWidget()
        bl = QVBoxLayout(self._body)
        bl.setContentsMargins(28, 4, 28, 24)
        bl.setSpacing(12)

        prods = db.products_all()
        self.stat_lbl = QLabel(f"{len(prods)}  PRODUK  PAKAN  TERSEDIA")
        self.stat_lbl.setObjectName("SectionH")
        bl.addWidget(self.stat_lbl)

        # jumlah kolom adaptif (3-5 kolom) — pakai lebar WINDOW karena
        # lebar halaman belum final saat reload dipicu showEvent
        w_win = self.window().width() if self.window() else 1600
        cols = max(3, min(5, (w_win - 340) // 300)) if w_win > 800 else 2

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 6, 0, 0)
        grid.setSpacing(14)

        rows = (len(prods) + cols - 1) // cols
        for i, p in enumerate(prods):
            card = QFrame()
            card.setObjectName("Card")
            card.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                                stop:0 rgba(17,32,55,0.92),
                                stop:1 rgba(10,19,36,0.94));
                    border: 1px solid #173252; border-radius: 14px;
                }
                QLabel { border: none; background: transparent; }
            """)
            card.setFixedSize(280, 200)
            vl = QVBoxLayout(card)
            vl.setContentsMargins(18, 14, 18, 14)
            vl.setSpacing(6)
            # foto produk referensi sesuai bentuk (pellet/serbuk)
            bkey = str(p.get("bentuk") or "pelet").lower()
            bkey = "serbuk" if "serbuk" in bkey or "bubuk" in bkey else "pellet"
            top = QHBoxLayout()
            top.setSpacing(10)
            pic = PhotoImage(bkey, subdir="products", emoji="🧺",
                             size=52, radius=10)
            top.addWidget(pic, 0, Qt.AlignTop)
            tcol = QVBoxLayout()
            tcol.setSpacing(4)
            nm = QLabel(p["nama"])
            nm.setStyleSheet(f"font-family:{theme.DISPLAY_FONT}; font-size:14px;"
                             "font-weight:700;")
            nm.setWordWrap(True)
            tcol.addWidget(nm)
            mrt = QLabel(f"{p['merek'] or '-'}  •  {p['bentuk']}  {p['ukuran'] or ''}"
                         .strip())
            mrt.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
            tcol.addWidget(mrt)
            tcol.addStretch()
            top.addLayout(tcol, 10)
            vl.addLayout(top)
            vl.addStretch()
            if str(p.get("catatan") or ""):
                ct = QLabel(str(p["catatan"]))
                ct.setWordWrap(True)
                ct.setStyleSheet(f"color:{MUTED}; font-size:10px;")
                vl.addWidget(ct)
            rowg = QHBoxLayout()
            pr = QLabel("Rp {:,.0f}".format(float(p["harga"])).replace(",", "."))
            pr.setStyleSheet(f"font-family:{theme.DISPLAY_FONT}; font-size:19px;"
                             f"color:{ACCENT}; font-weight:800;")
            rowg.addWidget(pr)
            rowg.addStretch()
            st = QLabel("✔ STOK ADA" if int(p["stok"]) > 0 else "✖ KOSONG")
            st.setStyleSheet(f"font-size:10px; font-weight:700; color:"
                             f"{GOOD if int(p['stok']) > 0 else BAD};")
            rowg.addWidget(st)
            vl.addLayout(rowg)
            grid.addWidget(card, i // cols, i % cols)
        # dorong konten ke atas (baris tidak melar tinggi)
        grid.setRowStretch(rows, 10)
        for c in range(cols):
            grid.setColumnStretch(c, 1)
        grid.setColumnStretch(cols, 0)
        self._last_cols = cols

        scroll.setWidget(holder)
        bl.addWidget(scroll, 10)
        self._rot.addWidget(self._body, 10)


# =====================================================================
# 5. ADMIN
# =====================================================================
PIN_MASK = "•"

class AdminGate(QWidget):
    """Halaman input PIN admin."""
    unlock = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        from app.core import database as _db
        self.pin = _db.get_config().get("admin_pin", "2026")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)

        wrap = QFrame()
        wrap.setObjectName("Card")
        wrap.setFixedSize(360, 260)
        wrap.setStyleSheet("""
            QFrame#Card { background: rgba(13,31,51,0.95);
                          border:1px solid #123252; border-radius:16px; }
            QFrame#Card QLabel { border:none; }
        """)
        wl = QVBoxLayout(wrap)
        wl.setSpacing(14)
        wl.setAlignment(Qt.AlignCenter)
        icon = PlaceholderIcon("🔒", 64)
        icon.setAlignment(Qt.AlignCenter)
        wl.addWidget(icon, 0, Qt.AlignHCenter)
        t = QLabel("MODE  ADMIN")
        t.setObjectName("SectionH")
        wl.addWidget(t, 0, Qt.AlignHCenter)
        s = QLabel("Masukkan PIN khusus pemilik toko")
        s.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        wl.addWidget(s, 0, Qt.AlignHCenter)
        self.pin_edit = QLineEdit()
        self.pin_edit.setEchoMode(QLineEdit.Password)
        self.pin_edit.setPlaceholderText("PIN")
        self.pin_edit.setFixedSize(200, 40)
        self.pin_edit.setAlignment(Qt.AlignCenter)
        self.pin_edit.returnPressed.connect(self._try)
        wl.addWidget(self.pin_edit, 0, Qt.AlignHCenter)
        b = QBtn("BUKA  ▸", primary=True)
        b.setFixedSize(200, 40)
        b.clicked.connect(self._try)
        wl.addWidget(b, 0, Qt.AlignHCenter)
        self.err = QLabel("")
        self.err.setStyleSheet(f"color:{BAD}; font-size:11px;")
        wl.addWidget(self.err, 0, Qt.AlignHCenter)
        lay.addWidget(wrap, 0, Qt.AlignHCenter)

    def _try(self):
        if self.pin_edit.text() == self.pin:
            self.err.setText("")
            self.pin_edit.clear()
            self.unlock.emit()
        else:
            self.err.setText("PIN salah, coba lagi.")


class AdminPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        rot = QVBoxLayout(self)
        rot.setContentsMargins(0, 0, 0, 0)
        rot.addWidget(_make_back_bar("PANEL  ADMIN", lambda: self.window().go_page("standby")))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_products(), "◈  KATALOG PAKAN")
        self.tabs.addTab(self._tab_recs(), "◈  REKOMENDASI")
        self.tabs.addTab(self._tab_settings(), "◈  SISTEM")
        rot.addWidget(self.tabs, 10)

        # refresh pin dari config
        QTimer.singleShot(50, self._reload_settings)

    # ---------------- tab katalog ----------------
    def _tab_products(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 20)
        lay.setSpacing(10)

        h = QLabel("KELOLA PRODUK PAKAN YANG DIJUAL DI TOKOMU")
        h.setObjectName("SectionH")
        lay.addWidget(h)

        self.tbl = QTableWidget()
        self.tbl.setColumnCount(8)
        self.tbl.setHorizontalHeaderLabels(["ID", "NAMA", "MEREK", "BENTUK",
                                            "UKURAN", "PROTEIN", "HARGA", "STOK"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tbl, 10)

        bars = QHBoxLayout()
        b_add = QBtn("＋ Tambah Baris")
        b_add.clicked.connect(self._add_row)
        b_del = QBtn("— Hapus Terpilih", danger=True)
        b_del.clicked.connect(self._del_row)
        b_save = QBtn("✓  SIMPAN SEMUA", primary=True)
        b_save.clicked.connect(self._save_products)
        bars.addWidget(b_add)
        bars.addWidget(b_del)
        bars.addStretch()
        bars.addWidget(b_save)
        lay.addLayout(bars)
        self._load_products()
        return w

    def _load_products(self):
        conn = db.get_conn()
        rows = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY nama")]
        conn.close()
        self.tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(["id", "nama", "merek", "bentuk", "ukuran",
                                     "protein", "harga", "stok"]):
                it = QTableWidgetItem(str(r[key]))
                if key == "id":
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.tbl.setItem(i, j, it)

    def _add_row(self):
        self.tbl.setRowCount(self.tbl.rowCount() + 1)
        for j in range(self.tbl.columnCount()):
            self.tbl.setItem(self.tbl.rowCount() - 1, j,
                             QTableWidgetItem("" if j > 0 else "(baru)"))

    def _del_row(self):
        row = self.tbl.currentRow()
        if row >= 0:
            pid = self.tbl.item(row, 0).text()
            conn = db.get_conn()
            if self.tbl.item(row, 0).text() != "(baru)":
                conn.execute("DELETE FROM products WHERE id=?", (pid,))
                conn.execute("DELETE FROM rekomendasi WHERE product_id=?", (pid,))
            conn.commit()
            conn.close()
            self._load_products()

    def _save_products(self):
        conn = db.get_conn()
        new_rows, update_rows = [], []
        for i in range(self.tbl.rowCount()):
            vals = {
                "nama":  self.tbl.item(i, 1).text() if self.tbl.item(i, 1) else "",
                "merek": self.tbl.item(i, 2).text() if self.tbl.item(i, 2) else "",
                "bentuk": self.tbl.item(i, 3).text() if self.tbl.item(i, 3) else "pelet",
                "ukuran": self.tbl.item(i, 4).text() if self.tbl.item(i, 4) else "",
                "protein": float(self.tbl.item(i, 5).text() or 0),
                "harga": float(self.tbl.item(i, 6).text() or 0),
                "stok": int(self.tbl.item(i, 7).text() or 0),
            }
            if not vals["nama"]:
                continue
            pid = self.tbl.item(i, 0).text() if self.tbl.item(i, 0) else ""
            if pid == "(baru)" or not pid.isdigit():
                new_rows.append(vals)
            else:
                update_rows.append((vals, int(pid)))
        for v, pid in update_rows:
            conn.execute("""UPDATE products SET nama=?, merek=?, bentuk=?, ukuran=?,
                            protein=?, harga=?, stok=? WHERE id=?""",
                         (v["nama"], v["merek"], v["bentuk"], v["ukuran"],
                          v["protein"], v["harga"], v["stok"], pid))
        for v in new_rows:
            conn.execute("""INSERT INTO products (nama, merek, bentuk, ukuran, protein,
                            harga, stok) VALUES (?,?,?,?,?,?,?)""",
                         (v["nama"], v["merek"], v["bentuk"], v["ukuran"],
                          v["protein"], v["harga"], v["stok"]))
        conn.commit()
        conn.close()
        self._load_products()

    # ---------------- tab rekomendasi ----------------
    def _tab_recs(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 20)
        h = QLabel("ATUR REKOMENDASI PAKAN PER JENIS IKAN (urut prioritas 1→3)")
        h.setObjectName("SectionH")
        lay.addWidget(h)

        self.rec_scroll = QScrollArea()
        self.rec_scroll.setWidgetResizable(True)
        self.rec_scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        self.rec_grid = QGridLayout(holder)
        self.rec_grid.setContentsMargins(12, 10, 12, 10)
        self.rec_grid.setSpacing(10)
        self.rec_scroll.setWidget(holder)
        lay.addWidget(self.rec_scroll, 10)

        b_save = QBtn("✓  SAVE REKOMENDASI", primary=True)
        b_save.clicked.connect(self._save_recs)
        lay.addWidget(b_save)

        self._rec_cbs = []          # [(species_id, [cb1, cb2, cb3])]
        QTimer.singleShot(80, self._load_recs)
        return w

    def _load_recs(self):
        conn = db.get_conn()
        species = [dict(r) for r in conn.execute("SELECT * FROM species ORDER BY display_name")]
        products = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY nama")]
        recs = [dict(r) for r in conn.execute("SELECT * FROM rekomendasi")]
        conn.close()

        self.grid_loc = None
        # clear grid
        while self.rec_grid.count():
            it = self.rec_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._rec_cbs = []

        for j, head in enumerate(["JENIS IKAN", "PRIORITAS 1", "PRIORITAS 2", "PRIORITAS 3"]):
            lab = QLabel(head)
            lab.setStyleSheet(f"color:{ACCENT_2}; font-weight:700; font-size:11px;"
                              "letter-spacing:1px;")
            self.rec_grid.addWidget(lab, 0, j)

        for i, sp in enumerate(species, 1):
            nm = QLabel(f"{sp['emoji']} {sp['display_name']}")
            nm.setStyleSheet("font-weight:700;")
            self.rec_grid.addWidget(nm, i, 0)
            cbs = []
            for prio in (1, 2, 3):
                cb = QComboBox()
                cb.addItem("(kosong)", None)
                for p in products:
                    cb.addItem(p["nama"] + "  •  " + str(p.get("ukuran") or ""), p["id"])
                cur = next((r for r in recs
                            if r["species_id"] == sp["id"] and r["priority"] == prio), None)
                if cur:
                    for k in range(cb.count()):
                        if cb.itemData(k) == cur["product_id"]:
                            cb.setCurrentIndex(k)
                cbs.append(cb)
                self.rec_grid.addWidget(cb, i, prio)
            self._rec_cbs.append((sp["id"], cbs))
            self.rec_grid.setRowStretch(i, 1) if False else None

    def _save_recs(self):
        conn = db.get_conn()
        conn.execute("DELETE FROM rekomendasi")
        for sp_id, cbs in self._rec_cbs:
            for prio, cb in enumerate(cbs, 1):
                pid = cb.currentData()
                if pid:
                    conn.execute("""INSERT INTO rekomendasi (species_id, product_id, priority)
                                    VALUES (?,?,?)""", (sp_id, pid, prio))
        conn.commit()
        conn.close()

    # ---------------- tab settings (kamera & sistem) ----------------
    def _tab_settings(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 20)
        lay.setSpacing(10)
        h = QLabel("PENGATURAN KAMERA & MESIN DETEKSI")
        h.setObjectName("SectionH")
        lay.addWidget(h)

        form = QFrame()
        form.setObjectName("Card")
        form.setStyleSheet("QFrame#Card { background: rgba(13,31,51,0.92);"
                           " border: 1px solid #123252; border-radius: 14px; }")
        fl = QGridLayout(form)
        fl.setContentsMargins(20, 18, 20, 18)
        fl.setSpacing(12)

        def lab(text):
            l = QLabel(text)
            l.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
            return l

        # --- sumber kamera ---
        self.s_source = QComboBox()
        self.s_source.addItem("Webcam Laptop / USB", "webcam")
        self.s_source.addItem("DroidCam HP (WiFi)", "droidcam")
        fl.addWidget(lab("SUMBER KAMERA"), 0, 0)
        fl.addWidget(self.s_source, 0, 1)

        # --- webcam device + tombol scan ---
        self.s_device = QComboBox()
        self.s_device.addItem("(klik DETEKSI untuk melihat daftar)", None)
        self.s_device.setMinimumWidth(320)
        fl.addWidget(lab("KAMERA WEBCAM TERDETEKSI"), 1, 0)
        fl.addWidget(self.s_device, 1, 1)

        self.b_scan = QBtn("🔍  DETEKSI KAMERA")
        self.b_scan.clicked.connect(self._scan_cameras)
        self.scan_lbl = QLabel("")
        self.scan_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        fl.addWidget(self.b_scan, 2, 0)
        fl.addWidget(self.scan_lbl, 2, 1)

        # --- droidcam ---
        self.s_url = QLineEdit()
        self.s_url.setPlaceholderText("http://192.168.1.xx:4747/video")
        fl.addWidget(lab("URL DROIDCAM"), 3, 0)
        fl.addWidget(self.s_url, 3, 1)

        # --- deteksi & lainnya ---
        self.s_conf = QDoubleSpinBox()
        self.s_conf.setRange(0.30, 0.95)
        self.s_conf.setSingleStep(0.05)
        self.s_conf.setPrefix("≥ ")
        fl.addWidget(lab("AMBATAS KEPERCAYAAN DETEKSI"), 4, 0)
        fl.addWidget(self.s_conf, 4, 1)

        self.s_pin = QLineEdit()
        self.s_pin.setEchoMode(QLineEdit.Password)
        fl.addWidget(lab("PIN ADMIN BARU"), 5, 0)
        fl.addWidget(self.s_pin, 5, 1)

        self.s_store = QLineEdit()
        fl.addWidget(lab("NAMA TOKO (TAMPIL DI HEADER)"), 6, 0)
        fl.addWidget(self.s_store, 6, 1)

        lay.addWidget(form)

        # --- preview tes kamera ---
        prev_card = QFrame()
        prev_card.setObjectName("Card")
        prev_card.setStyleSheet("QFrame#Card { background: rgba(13,31,51,0.92);"
                                " border: 1px solid #123252; border-radius: 14px; }")
        pl = QHBoxLayout(prev_card)
        pl.setContentsMargins(20, 16, 20, 16)
        self.preview_lbl = QLabel("PREVIEW\n\nTEKAN [TES KAMERA], TUNGGU 5 DETIK,\n"
                                  "Gambar SIAP muncul di sini.")
        self.preview_lbl.setAlignment(Qt.AlignCenter)
        self.preview_lbl.setFixedSize(400, 280)
        self.preview_lbl.setStyleSheet("""
            background: #04101C; border: 1px solid #123252;
            border-radius: 10px; font-size: 13px; color: #64748B;
        """)
        pl.addWidget(self.preview_lbl)
        right = QVBoxLayout()
        right.setSpacing(10)
        self.b_preview = QBtn("▶  TES KAMERA (LIVE 15 DETIK)", primary=True)
        self.b_preview.clicked.connect(self._toggle_preview)
        right.addWidget(self.b_preview)
        self.preview_stat = QLabel("Kamera diuji dengan pengaturan di atas.")
        self.preview_stat.setWordWrap(True)
        self.preview_stat.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        right.addWidget(self.preview_stat)
        right.addStretch()
        pl.addLayout(right, 10)
        lay.addWidget(prev_card)

        # --- bar save ---
        b_save = QBtn("✓  SIMPAN PENGATURAN  (+ RELOAD KAMERA)", primary=True)
        b_save.clicked.connect(self._save_settings)
        lay.addWidget(b_save)

        self._pv_src = None
        self._pv_timer = None
        self._pv_deadline = 0
        self.s_source.currentIndexChanged.connect(self._reload_device_visibility)
        QTimer.singleShot(50, self._reload_settings)
        QTimer.singleShot(120, self._scan_cameras)     # scan otomatis saat buka tab? (dipanggil via singleShot utk pertama)
        return w

    # ---------- scan kamera ----------
    def _scan_cameras(self):
        if getattr(self, "_scan_running", False):
            return
        self._scan_running = True
        self.b_scan.setEnabled(False)
        self.b_scan.setText("... TERDETEKSI ...")
        self.scan_lbl.setText("Mengintip semua port kamera (±5 detik)...")
        self._scan_thread = CameraScanThread(self)   # parent=self: hindari GC saat jalan
        self._scan_thread.found.connect(self._scan_done)
        self._scan_thread.start()

    def _scan_done(self, cams):
        self._scan_running = False
        self.b_scan.setEnabled(True)
        self.b_scan.setText("🔍  DETEKSI KAMERA")
        keep = self.s_device.currentData()
        self.s_device.blockSignals(True)
        self.s_device.clear()
        if cams:
            for c in cams:
                label = f"{c['backend']}  #{c['index']}   ({c['size'][0]}x{c['size'][1]})"
                self.s_device.addItem(label, f"{c['backend']}|{c['index']}")
            self.scan_lbl.setText(f"✔ {len(cams)} webcam terdeteksi — pilih salah satu")
        else:
            self.s_device.addItem("(tidak ada webcam terdeteksi)", None)
            self.scan_lbl.setText("✖ Webcam tidak terdeteksi — cek izin kamera Windows "
                                  "atau fisik webcam (tombol Fn+F9 di Lenovo).")
        self.s_device.blockSignals(False)
        if keep:
            for i in range(self.s_device.count()):
                if self.s_device.itemData(i) == keep:
                    self.s_device.setCurrentIndex(i)
                    break

    # ---------- preview tes ----------
    def _toggle_preview(self):
        if self._pv_src is not None:
            self._stop_preview()
            return
        src = self.s_source.currentData()
        backend, index = "DSHOW", "0"
        dev = self.s_device.currentData()
        if src == "webcam":
            if dev:
                backend, index = dev.split("|")
            from app.core.database import get_config as _gcfg
            cfg = _gcfg()
            index = index if dev else cfg.get("camera_index", "0")
            backend = backend if dev else cfg.get("camera_backend", "DSHOW")
        from app.core.camera import CameraSource
        from app.core.logs import log
        pv = CameraSource(source=src, index=index,
                          url=self.s_url.text().strip(), backend=backend)
        self._pv_src = pv
        self.b_preview.setEnabled(False)
        self.b_preview.setText("... MENYALAKAN KAMERA ...")
        self.preview_stat.setText(f"Menyambung: {src}"
                                  + (f" [{backend} #{index}]" if src == "webcam" else "")
                                  + " ...")
        self._pv_starter = _PreviewStarter(pv)
        self._pv_starter.ready.connect(self._preview_ready)
        self._pv_starter.start()

    def _preview_ready(self, ok, detail):
        self.b_preview.setEnabled(True)
        self.b_preview.setText("■  STOP TES")
        if not ok:
            self.preview_stat.setStyleSheet(f"color:{BAD}; font-size:11px;")
            self.preview_stat.setText("✖ GAGAL: " + detail)
            self._stop_preview()
            return
        self.preview_stat.setStyleSheet(f"color:{GOOD}; font-size:11px;")
        self.preview_stat.setText("✔ Kamera hidup: " + detail)
        self._pv_deadline = 15
        self._pv_timer = QTimer(self)
        self._pv_timer.timeout.connect(self._pv_tick)
        self._pv_timer.start(50)
        QTimer.singleShot(15000, self._stop_preview)

    def _pv_tick(self):
        frame = self._pv_src.read()
        if frame is not None:
            pm = cv2_to_pixmap(frame)
            self.preview_lbl.setPixmap(pm.scaled(
                self.preview_lbl.width(), self.preview_lbl.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _stop_preview(self):
        if self._pv_timer is not None:
            self._pv_timer.stop()
            self._pv_timer = None
        if self._pv_src is not None:
            try:
                self._pv_src.stop()
            except Exception:
                pass
            self._pv_src = None
        if hasattr(self, "_pv_starter") and self._pv_starter is not None:
            if not self._pv_starter.isFinished():
                try:
                    self._pv_starter.terminate()
                except Exception:
                    pass
            self._pv_starter = None
        self.b_preview.setText("▶  TES KAMERA (LIVE 15 DETIK)")

    def stop_preview(self):
        """Dipanggil dari MainWindow saat page berubah / app ditutup."""
        self._stop_preview()

    def _reload_device_visibility(self):
        src = self.s_source.currentData()
        self.s_device.setEnabled(src == "webcam")
        self.b_scan.setEnabled(src == "webcam")
        self.s_url.setPlaceholderText(
            "http://IP-HP:4747/video  — cek angka di app DroidCam"
            if src == "droidcam" else "http://192.168.1.xx:4747/video")

    def _reload_settings(self):
        cfg = db.get_config()
        idx = 0 if cfg.get("camera_source", "webcam") == "webcam" else 1
        self.s_source.setCurrentIndex(idx)
        self.s_url.setText(cfg.get("droidcam_url", ""))
        try:
            self.s_conf.setValue(float(cfg.get("conf_threshold", "0.55")))
        except Exception:
            self.s_conf.setValue(0.55)
        self.s_pin.setPlaceholderText("(biarkan kosong = tidak mengubah PIN)")
        self.s_store.setText(cfg.get("store_name", ""))
        # preload pilihan kamera tersimpan
        want = f"{cfg.get('camera_backend','DSHOW')}|{cfg.get('camera_index','0')}"
        found_at = None
        for i in range(self.s_device.count()):
            if self.s_device.itemData(i) == want:
                found_at = i
                break
        if found_at is not None:
            self.s_device.setCurrentIndex(found_at)

    def _save_settings(self):
        conn = db.get_conn()
        src = self.s_source.currentData()
        db.set_config(conn, "camera_source", src)
        if src == "webcam":
            dev = self.s_device.currentData()
            if dev:
                backend, index = dev.split("|")
                db.set_config(conn, "camera_backend", backend)
                db.set_config(conn, "camera_index", index)
        db.set_config(conn, "droidcam_url", self.s_url.text().strip())
        db.set_config(conn, "conf_threshold", str(self.s_conf.value()))
        if self.s_pin.text().strip():
            db.set_config(conn, "admin_pin", self.s_pin.text().strip())
        db.set_config(conn, "store_name", self.s_store.text().strip())
        conn.close()
        # refresh PIN di gate
        main = self.window()
        if hasattr(main, "apply_settings_reload"):
            main.apply_settings_reload()


class CameraScanThread(QThread):
    """Deteksi webcam Windows di thread background (biar UI tidak freeze)."""
    found = Signal(list)

    def run(self):
        from app.core.camera import enumerate_webcams
        try:
            self.found.emit(enumerate_webcams())
        except Exception:
            self.found.emit([])


class _PreviewStarter(QThread):
    ready = Signal(bool, str)

    def __init__(self, cam_source, parent=None):
        super().__init__(parent)
        self._cs = cam_source

    def run(self):
        try:
            ok = self._cs.start()
            self.ready.emit(bool(ok), getattr(self._cs, "status_detail", ""))
        except Exception as e:
            self.ready.emit(False, str(e))
