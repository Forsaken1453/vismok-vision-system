"""Jendela utama Leviathan + loop kamera/deteksi.

v2: sidebar navigasi, HUD detail deteksi live, riwayat tersimpan di DB,
kamera async + auto-retry, overlay offline.
"""
import os
import datetime

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QSpinBox, QStackedWidget,
                               QVBoxLayout, QWidget)

from app.config import SNAP_DIR, BASE_DIR
from app.core import database as db
from app.core.camera import CameraSource
from app.core.detector import load_detector
from app.core.logs import log
from app.ui import theme
from app.ui.widgets import cv2_to_pixmap
from app.ui.pages import (AdminGate, AdminPage, CatalogPage, DetailPage,
                          HistoryPage, ManualPage, QBtn, ResultPage,
                          Sidebar, StandbyPage)


class CartDialog(QDialog):
    """Keranjang checkout: pilih jumlah beli tiap produk rekomendasi."""

    def __init__(self, recs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KERANJANG  CHECKOUT")
        self.setModal(True)
        self.setFixedSize(520, 130 + 62 * len(recs))
        self.setStyleSheet("""
            QDialog { background: #0A1220; }
            QLabel#DTitle { color: #22D3EE; font-family: Orbitron;
                font-size: 16px; font-weight: 800; letter-spacing: 3px; }
            QLabel#DHint  { color: #7FB6D9; font-size: 11px; }
            QLabel#DProd  { color: #EAF6FF; font-size: 13px; font-weight: 600; }
            QLabel#DSub   { color: #7FA8C9; font-size: 10px; }
            QLabel#DPrice { color: #34D399; font-size: 12px; font-weight: 700; }
            QLabel#DTotLbl{ color: #9DB2C7; font-size: 12px; letter-spacing: 1px; }
            QLabel#DTotVal{ color: #22D3EE; font-family: Orbitron;
                font-size: 18px; font-weight: 800; }
            QSpinBox { background: #101C2E; color: #EAF6FF;
                border: 1px solid #1E4B6E; border-radius: 6px;
                padding: 4px 8px; font-size: 13px; min-width: 64px; }
            QSpinBox::up-button, QSpinBox::down-button {
                background: #16324D; width: 18px; }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 16)
        lay.setSpacing(8)
        t = QLabel("KERANJANG  CHECKOUT")
        t.setObjectName("DTitle")
        lay.addWidget(t)
        h = QLabel("Pilih jumlah yang mau dibeli pembeli (0 = tidak dibeli),"
                   " lalu tekan EXPORT PDF.")
        h.setObjectName("DHint")
        h.setWordWrap(True)
        lay.addWidget(h)

        self._spins = []
        self._prices = []
        self._recs_cache = list(recs)
        for r in recs:
            row = QHBoxLayout()
            row.setSpacing(10)
            col = QVBoxLayout()
            col.setSpacing(1)
            nm = QLabel(str(r.get("nama", "")))
            nm.setObjectName("DProd")
            col.addWidget(nm)
            sub = QLabel(f"{r.get('bentuk') or ''} {r.get('ukuran') or ''}"
                         f"  •  dosis: {r.get('dosis') or '-'}")
            sub.setObjectName("DSub")
            sub.setWordWrap(True)
            col.addWidget(sub)
            row.addLayout(col, 1)
            pr = QLabel("Rp {:,.0f}".format(float(r.get("harga") or 0)).replace(",", "."))
            pr.setObjectName("DPrice")
            row.addWidget(pr)
            sp = QSpinBox()
            sp.setRange(0, 99)
            sp.setValue(1)
            sp.valueChanged.connect(self._update_total)
            self._spins.append(sp)
            self._prices.append(float(r.get("harga") or 0))
            row.addWidget(sp)
            lay.addLayout(row)

        lay.addSpacing(6)
        tot_row = QHBoxLayout()
        tl = QLabel("TOTAL")
        tl.setObjectName("DTotLbl")
        tot_row.addWidget(tl)
        tot_row.addStretch()
        self._tot = QLabel("Rp 0")
        self._tot.setObjectName("DTotVal")
        tot_row.addWidget(self._tot)
        lay.addLayout(tot_row)

        btns = QHBoxLayout()
        btns.addStretch()
        b_cancel = QBtn("BATAL")
        b_cancel.clicked.connect(self.reject)
        btns.addWidget(b_cancel)
        b_ok = QBtn("🖨  EXPORT PDF", primary=True, big=True)
        b_ok.clicked.connect(self.accept)
        btns.addWidget(b_ok)
        lay.addLayout(btns)
        self._update_total()

    def _update_total(self):
        tot = sum(q * pr for q, pr in zip(
            (s.value() for s in self._spins), self._prices))
        self._tot.setText("Rp {:,.0f}".format(tot).replace(",", "."))

    def items(self):
        """Return rekomendasi dgn qty (hanya yg > 0)."""
        out = []
        for sp, r in zip(self._spins, self._recs_cache):
            q = sp.value()
            if q > 0:
                it = dict(r)
                it["qty"] = q
                out.append(it)
        return out


class ConnectorThread(QThread):
    """Jalankan cs.start() di thread terpisah (open kamera bisa blok berdetik)."""
    done = Signal(bool, str)

    def __init__(self, cam_source, parent=None):
        super().__init__(parent)
        self._cs = cam_source

    def run(self):
        try:
            ok = self._cs.start()
            self.done.emit(bool(ok), getattr(self._cs, "status_detail", ""))
        except Exception as e:
            self.done.emit(False, f"exception: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VISMOK ASELI NGAWI — Asisten Vision Pakan Ikan")
        self.setStyleSheet(theme.QSS)

        # ---- data ----
        self._reload_cfg_and_species()

        # ---- layout utama: Sidebar | Pages ----
        central = QWidget()
        hl = QHBoxLayout(central)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        self.sidebar = Sidebar()
        self.sidebar.nav.connect(self._nav)
        hl.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        hl.addWidget(self.pages, 10)
        self.setCentralWidget(central)

        # ---- pages ----
        self.page_standby = StandbyPage()
        self.page_result = ResultPage()
        self.page_detail = DetailPage()
        self.page_manual = ManualPage(mode="result")
        self.page_manual.set_species_list(self.species)
        self.page_library = ManualPage(mode="detail")
        self.page_library.set_species_list(self.species)
        self.page_history = HistoryPage()
        self.page_catalog = CatalogPage()
        self.page_admin_gate = AdminGate()
        self.page_admin = AdminPage()
        for w in (self.page_standby, self.page_result, self.page_detail,
                  self.page_manual, self.page_library, self.page_history,
                  self.page_catalog, self.page_admin_gate, self.page_admin):
            self.pages.addWidget(w)
        self.PAGES = {
            "kamera": 0, "result": 1, "detail": 2, "manual": 3, "library": 4,
            "history": 5, "catalog": 6, "admin": 7, "admin_main": 8,
        }
        self.go_page("kamera")

        self.page_admin_gate.unlock.connect(self._admin_unlocked)
        self.page_standby.camera_retry.connect(self.retry_camera)
        self.page_standby.source_picked.connect(self._on_source_picked)
        self.page_standby.mode_picked.connect(self._on_mode_picked)
        self.page_standby.manual_scan.connect(self._manual_scan)
        self.page_result.pdf_export.connect(self._export_pdf)
        self.page_history.clear_requested.connect(self._clear_history)
        self.page_standby.droid_ip_request.connect(self._droid_ip_dialog)

        # ---- loop deteksi ----
        self.camera_source = None
        self._last_frame = None
        self._frame_count = 0
        self._fps_count = 0
        self._fps_shown = 0
        self._fps_last_t = None
        self._confirm_counter = {}
        self._need_confirm = 2          # harus terdeteksi 2x berturut utk konfirmasi
        self._connector = None
        self._retry_count = 0
        self._retry_timer = None
        self._fps_chip_last = ""
        self._snap_count = 0
        self._stall_ticks = 0           # watchdog: kamera "OK" tapi tidak ada frame
        self._failed_retry_armed = False
        self.detection_mode = self.cfg.get("detection_mode", "auto")
        self._last_snap_fn = ""

        self._init_detector()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._loop)
        self._timer.start(33)           # ~30 fps scheduling
        self._apply_camera()

        self.page_standby.set_source_active(
            self.cfg.get("camera_source", "webcam"))
        self.page_standby.set_mode_active(self.detection_mode)
        self._update_store_label()

    # ------------------------------------------------------------------
    def _reload_cfg_and_species(self):
        self.cfg = db.get_config()
        self.species = db.species_all()
        self.class_names = [sp["class_name"] for sp in self.species]

    def _update_store_label(self):
        store = (self.cfg.get("store_name") or "").strip()
        try:
            self.page_standby.hint.setText(
                f"{store}  ▸  DEKATKAN IKAN KE KAMERA".upper()
                if store else "DEKATKAN  IKAN  KE  KAMERA  ▸  DETEKSI  OTOMATIS")
            self.page_standby.hint.setToolTip(f"Lokasi exe: {BASE_DIR}")
        except Exception:
            pass

    def _init_detector(self):
        try:
            conf = float(self.cfg.get("conf_threshold", "0.55"))
        except (TypeError, ValueError):
            conf = 0.55
        self.confirm_threshold = conf
        try:
            imgsz = int(self.cfg.get("imgsz", "640") or 640)
        except (TypeError, ValueError):
            imgsz = 640
        self.detector = load_detector(self.class_names, imgsz=imgsz,
                                      conf=max(0.35, conf - 0.15))
        self.page_standby.chip_model.set_ok(True, f"MODEL: {self.detector.name}")

    # ---------------- navigasi ----------------
    def go_page(self, name):
        idx = self.PAGES.get(name, 0)
        # stop preview saat keluar/masuk admin
        if name not in ("admin", "admin_main"):
            try:
                self.page_admin.stop_preview()
            except Exception:
                pass
        self.pages.setCurrentIndex(idx)
        nav_key = {"kamera": "kamera", "manual": "kamera", "result": "kamera",
                   "detail": "kamera", "library": "library",
                   "history": "history", "catalog": "catalog",
                   "admin": "admin", "admin_main": "admin"}.get(name, name)
        self.sidebar.set_active(nav_key)
        # reload dinamis utk halaman data-driven
        if name == "history":
            self.page_history.reload()
        # catalog: rebuild ditangani showEvent CatalogPage

    def _nav(self, key):
        self.go_page(key)

    def select_manual(self, species):
        self.page_result.set_result(species, None, conf=None)
        self.go_page("result")

    def show_detail(self, species):
        self.page_detail.set_species(species)
        self.go_page("detail")

    # ---------------- kamera: async connect & retry ----------------
    def _apply_camera(self):
        if self._timer is None:
            return
        self._timer.stop()

        # buang connector lama (sinyal dibuang via guard)
        self._connector = None
        if self.camera_source is not None:
            try:
                self.camera_source.stop()
            except Exception:
                pass
            self.camera_source = None
        self.page_standby.camera.clear()

        self.page_standby.chip_cam.set_ok(False, "KAMERA: MENYALAKAN…")
        # PENTING (anti flashing): JANGAN sembunyikan overlay OFFLINE
        # saat siklus retry — kalau di-hide di sini dan di-show lagi
        # saat gagal, overlay merah seukuran layar berkedip tiap siklus
        # (yang dilihat user sebagai "glitch disco"). Overlay tetap
        # tampil sampai kamera benar-benar OK.
        if self.page_standby.offline.isVisible():
            self.page_standby.offline_detail.setText(
                f"Mencoba ulang #{self._retry_count + 1} …")
        log(f"connect kamera mulai: source={self.cfg.get('camera_source')} "
            f"index={self.cfg.get('camera_index')} "
            f"backend={self.cfg.get('camera_backend')} "
            f"url={self.cfg.get('droidcam_url')}")

        self._timer.start(33)
        cs = CameraSource(
            source=self.cfg.get("camera_source", "webcam"),
            index=str(self.cfg.get("camera_index", "0")),
            url=self.cfg.get("droidcam_url", ""),
            backend=self.cfg.get("camera_backend", "DSHOW"),
        )
        self.camera_source = cs
        self._connector = ConnectorThread(cs, parent=self)
        # hapus otomatis setelah benar2 selesai (finished) — aman utk Qt
        self._connector.finished.connect(self._connector.deleteLater)
        self._connector.done.connect(self._camera_connected)
        self._connector.start()

    def _camera_connected(self, ok, detail):
        # guard: buang sinyal dari connector yang sudah diganti (stale)
        if self._connector is None or self.sender() is not self._connector:
            return
        self._stall_ticks = 0
        if ok:
            self._retry_count = 0
            self.page_standby.chip_cam.set_ok(True, "KAMERA: OK")
            self.page_standby.show_camera_offline(False)
            log("connect kamera BERHASIL: " + str(detail))
        else:
            self.page_standby.chip_cam.set_ok(False, "KAMERA: OFFLINE")
            self._retry_count += 1
            delay = (5000, 8000, 15000, 30000)[min(self._retry_count - 1, 3)]
            # overlay tetap tampil, hanya teks detail yang diperbarui
            # (anti flashing - jangan show/hide berulang)
            self.page_standby.show_camera_offline(
                True, f"{detail}\nMencoba ulang #{self._retry_count} "
                      f"dalam {delay // 1000} detik …")
            if self._retry_timer is None:
                self._retry_timer = QTimer(self)
                self._retry_timer.setSingleShot(True)
                self._retry_timer.timeout.connect(self._auto_retry)
            self._retry_timer.start(delay)
            log(f"connect kamera GAGAL: {detail} (retry ke-{self._retry_count})")

    def _droid_ip_dialog(self):
        """Dialog sambung kamera HP (DroidCam) lewat IP WiFi - cepat,
        tanpa masuk Admin (IP selalu berganti tiap pindah WiFi)."""
        cur = (self.cfg.get("droidcam_url") or "http://192.168.1.10:4747/video")
        base = cur
        for pre in ("http://", "https://"):
            if base.startswith(pre):
                base = base[len(pre):]
                break
        if base.endswith("/video"):
            base = base[:-6]

        dlg = QDialog(self)
        dlg.setWindowTitle("SAMBUNG  KAMERA  HP")
        dlg.setModal(True)
        dlg.setFixedSize(540, 250)
        dlg.setStyleSheet("""
            QDialog { background: #0A1220; }
            QLabel#DTitle { color: #22D3EE; font-family: Orbitron;
                font-size: 15px; font-weight: 800; letter-spacing: 3px; }
            QLabel#DHint  { color: #7FB6D9; font-size: 11px; }
            QLabel#DStep  { color: #9DB2C7; font-size: 11px; }
            QLineEdit { background: #101C2E; color: #EAF6FF;
                border: 1px solid #22D3EE; border-radius: 8px;
                padding: 9px 12px; font-size: 15px;
                font-family: Consolas, monospace; }
        """)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 18, 24, 16)
        lay.setSpacing(8)
        t = QLabel("SAMBUNG  KAMERA  HP  (DROIDCAM)")
        t.setObjectName("DTitle")
        lay.addWidget(t)
        st = QLabel("1.  Buka aplikasi DroidCam di HP (biarkan jalan)\n"
                    "2.  HP & laptop harus satu WiFi\n"
                    "3.  Lihat IP di layar HP (contoh: 192.168.1.10:4747),"
                    " lalu isi di bawah:")
        st.setObjectName("DStep")
        lay.addWidget(st)
        ed = QLineEdit(base)
        ed.setPlaceholderText("192.168.1.10:4747")
        lay.addWidget(ed)
        hint = QLabel("IP akan disimpan otomatis - berikutnya cukup pilih"
                      " HP (DROIDCAM).")
        hint.setObjectName("DHint")
        lay.addWidget(hint)
        lay.addStretch()
        btns = QHBoxLayout()
        btns.addStretch()
        b_cancel = QBtn("BATAL")
        b_cancel.clicked.connect(dlg.reject)
        btns.addWidget(b_cancel)
        b_ok = QBtn("◈  SAMBUNG", primary=True, big=True)
        b_ok.clicked.connect(dlg.accept)
        btns.addWidget(b_ok)
        lay.addLayout(btns)
        if dlg.exec() != QDialog.Accepted:
            return

        ip = ed.text().strip().replace("http://", "").replace("https://", "")
        ip = ip.rstrip("/")
        if not ip:
            return
        if not ip.endswith("/video"):
            ip += "/video"
        url = "http://" + ip
        from app.core.database import get_conn, set_config
        conn = get_conn()
        set_config(conn, "droidcam_url", url)
        set_config(conn, "camera_source", "droidcam")
        conn.close()
        self._reload_cfg_and_species()
        self.page_standby.set_source_active("droidcam")
        log(f"droidcam URL baru: {url} - reconnect")
        self.retry_camera()
        self.statusbar_msg(f"Menyambung kamera HP: {url}")

    def _on_source_picked(self, key):
        """Pindah sumber kamera (laptop / droidcam / auto) → simpan & reconnect."""
        from app.core.database import get_conn, set_config
        conn = get_conn()
        set_config(conn, "camera_source", key)
        conn.close()
        self._reload_cfg_and_species()
        self.page_standby.set_source_active(key)
        self.retry_camera()

    def _failed_retry_go(self):
        self._failed_retry_armed = False
        if self.camera_source is not None and self.camera_source.status == "FAILED":
            self.retry_camera()

    def _on_mode_picked(self, key):
        """Ganti mode deteksi: auto (realtime) / manual (tombol)."""
        from app.core.database import get_conn, set_config
        conn = get_conn()
        set_config(conn, "detection_mode", key)
        conn.close()
        self.detection_mode = key
        self.page_standby.set_mode_active(key)
        log(f"mode deteksi -> {key}")

    def _manual_scan(self):
        """Tombol DETEKSI MANUAL: tangkap frame sekarang → inferensi → hasil."""
        if self.detection_mode != "manual":
            self._on_mode_picked("manual")
        frame = self._last_frame
        if frame is None:
            self.page_standby.chip_status.setText("● TIDAK ADA FRAME KAMERA")
            return
        dets, _ = self.detector.detect(frame)
        if not dets and hasattr(self.detector, "force"):
            dets = [self.detector.force()]          # mode demo: tetap kasih hasil
        if not dets:
            self.page_standby.chip_status.setText("● TIDAK ADA IKAN TERDETEKSI")
            return
        best = max(dets, key=lambda d: d["conf"])
        self._accept_detection(best)

    def retry_camera(self):
        self._retry_count = 0
        self._failed_retry_armed = False
        self._reload_cfg_and_species()
        self._apply_camera()

    def _auto_retry(self):
        if self.camera_source is None or not self.camera_source.is_open():
            self.retry_camera()

    def apply_settings_reload(self):
        self._reload_cfg_and_species()
        self.page_manual.set_species_list(self.species)
        self.page_library.set_species_list(self.species)
        self.page_admin_gate.pin = self.cfg.get("admin_pin", "2026")
        self._update_store_label()
        self._init_detector()
        self._apply_camera()

    # ------------------------------------------------------------------
    def _loop(self):
        if self.pages.currentWidget() is not self.page_standby:
            return                      # hemat CPU saat di halaman lain
        if self.camera_source is None:
            return

        # ambil status kamera (jgn bengkak) — refresh chip & HUD meta
        st = self.camera_source.status
        if st in ("RETRYING", "CONNECTING"):
            self.page_standby.chip_cam.set_ok(False, f"KAMERA: {st}…")
        elif st == "FAILED" and not self._failed_retry_armed:
            # thread internal gagal reconnect → paksa retry dari level utama
            self._failed_retry_armed = True
            self.page_standby.chip_cam.set_ok(False, "KAMERA: RETRYING…")
            log("deteksi status FAILED → auto-retry kamera")
            QTimer.singleShot(2500, self._failed_retry_go)

        frame = self.camera_source.read()
        if frame is None:
            # watchdog: kamera "open" tapi tidak pernah menghasilkan frame
            # (mis. resolusi -1x-1, perangkat dibajak proses lain) → retry
            if getattr(self.camera_source, "_opened_ok", False):
                self._stall_ticks += 1          # 1 tick ≈ 33 ms
                if self._stall_ticks >= 150:    # ~5 detik tanpa frame
                    self._stall_ticks = 0
                    log("watchdog: kamera open tapi tidak ada frame " +
                        "selama 5s → retry kamera")
                    self.retry_camera()
            return
        self._last_frame = frame
        self._frame_count += 1
        self._fps_count += 1

        # >>> render ke kamera view + HUD <<<
        pm = cv2_to_pixmap(frame)
        self.page_standby.camera.set_frame(pm)

        # FPS tiap 1 detik
        import time as _t
        now = _t.time()
        if self._fps_last_t is None:
            self._fps_last_t = now
        elif now - self._fps_last_t >= 1.0:
            self._fps_shown = round(self._fps_count / (now - self._fps_last_t))
            self._fps_count = 0
            self._fps_last_t = now
            txt = f"FPS: {self._fps_shown}"
            if txt != self._fps_chip_last:
                self._fps_chip_last = txt
                self.page_standby.chip_fps.set_ok(True, txt)

        # inferensi (ONNX tiap 3 frame biar halus)
        if getattr(self.detector, "name", "") == "ONNX" and self._frame_count % 3 != 0:
            dets, fps = [], 0.0
        else:
            dets, fps = self.detector.detect(frame)
        if dets is None:
            dets = []
        self.page_standby.camera.set_detections(dets)

        # update HUD detail
        model = self.detector.name
        thr = f"{self.confirm_threshold:.2f}"
        self.page_standby.update_hud(dets, fps=self._fps_shown or None,
                                     model=model, threshold=thr,
                                     snaps=None)

        # >>> logika konfirmasi deteksi utama (HANYA mode auto) <<<
        if self.detection_mode != "auto":
            return
        best = None
        if dets:
            best = max(dets, key=lambda d: d["conf"])
        if best is not None and best["conf"] >= self.confirm_threshold:
            key = best["class_name"]
            c = self._confirm_counter.get(key, 0) + 1
            self._confirm_counter = {key: c}
            self.page_standby.chip_status.setText(
                f"● {key.upper()} {c}/{self._need_confirm}")
            if c >= self._need_confirm:
                self._accept_detection(best)
                self._confirm_counter = {}
        else:
            self._confirm_counter = {}
            store = (self.cfg.get("store_name") or "").strip()
            self.page_standby.chip_status.setText(
                f"● SCANNING{(' — ' + store) if store else ''}")

    def statusbar_msg(self, text, ms=5000):
        """Toast notifikasi kecil di bawah-tengah jendela."""
        if getattr(self, "_toast", None) is None:
            from PySide6.QtWidgets import QLabel
            self._toast = QLabel(self)
            self._toast.setObjectName("Toast")
            self._toast.setStyleSheet("""
                QLabel#Toast {
                    background: rgba(10,22,38,0.94);
                    border: 1px solid #22D3EE;
                    border-radius: 10px;
                    padding: 10px 18px;
                    color: #EAF6FF;
                    font-size: 12px;
                }
            """)
            self._toast.setWordWrap(True)
            self._toast.setMaximumWidth(560)
            self._toast_timer = QTimer(self)
            self._toast_timer.timeout.connect(lambda: self._toast.hide())
        self._toast.setText(text)
        self._toast.adjustSize()
        self._toast.move(
            (self.width() - self._toast.width()) // 2,
            self.height() - self._toast.height() - 26)
        self._toast.show()
        self._toast.raise_()
        self._toast_timer.start(ms)

    def _export_pdf(self):
        """Keranjang checkout → kwitansi PDF (pilih jumlah beli tiap produk)."""
        sp = getattr(self.page_result, "_species", None)
        if not sp:
            return
        recs = db.recs_for_species(sp["id"]) if sp.get("id") else []
        if not recs:
            self.statusbar_msg("Tidak ada rekomendasi utk diekspor")
            return
        dlg = CartDialog(recs, self)
        if dlg.exec() != CartDialog.Accepted or not dlg.items():
            return
        try:
            from app.core.pdf_export import export_receipt
            snap = self._last_snap_fn
            if not (snap and os.path.isfile(snap)):
                snap = ""
            path = export_receipt(
                sp, self.page_result.conf_bar.value() / 100.0, dlg.items(),
                sp.get("tips") or [],
                (self.cfg.get("store_name") or "").strip(),
                snapshot_path=snap)
            log(f"PDF kwitansi: {path}")
            self.statusbar_msg(f"Kwitansi PDF tersimpan: {path}")
            os.startfile(path)          # buka PDF utk dikirim/cetak
        except Exception as e:
            log(f"EXPORT PDF GAGAL: {e!r}")
            self.statusbar_msg("Export PDF gagal - lihat log")

    def _clear_history(self):
        """Hapus semua riwayat deteksi (sudah dikonfirmasi di HistoryPage)."""
        try:
            n = db.detections_clear()
            self.page_history.reload()
            self._snap_count = 0
            log(f"riwayat dihapus ({n} baris)")
            self.statusbar_msg(f"Riwayat dihapus ({n} deteksi)")
        except Exception as e:
            log(f"HAPUS RIWAYAT GAGAL: {e!r}")
            self.statusbar_msg("Hapus riwayat gagal - lihat log")

    def _accept_detection(self, det):
        """Deteksi terkonfirmasi → snapshot → catat riwayat → halaman hasil."""
        species = next((sp for sp in self.species
                        if sp["class_name"] == det["class_name"]), None)
        if species is None:            # kelas model tdk ada di DB → pakai nama apa adanya
            species = {"id": None, "display_name": det["class_name"],
                       "emoji": "🐟", "deskripsi": "",
                       "class_name": det["class_name"], "tips": []}
        snap = cv2_to_pixmap(self._last_frame)
        snap_fn = ""
        try:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            snap_fn = f"det_{ts}_{det['class_name']}.jpg"
            path = os.path.join(SNAP_DIR, snap_fn)
            snap.save(path, quality=90)
            self._snap_count += 1
        except Exception:
            snap_fn = ""
        self._last_snap_fn = os.path.join(SNAP_DIR, snap_fn) if snap_fn else ""
        try:
            db.add_detection(det["class_name"], det["conf"], snap_fn)
        except Exception:
            pass
        self.page_result.set_result(species, snap, conf=det["conf"])
        self.go_page("result")

    # ------------------------------------------------------------------
    def keyPressEvent(self, ev):
        from PySide6.QtCore import Qt
        if ev.key() == Qt.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return
        super().keyPressEvent(ev)

    def _admin_unlocked(self):
        self.go_page("admin_main")

    def closeEvent(self, ev):
        try:
            self.page_admin.stop_preview()
        except Exception:
            pass
        try:
            if self.camera_source is not None:
                self.camera_source.stop()
        except Exception:
            pass
        try:
            if self._connector is not None and self._connector.isRunning():
                self._connector.wait(3000)
        except Exception:
            pass
        super().closeEvent(ev)
