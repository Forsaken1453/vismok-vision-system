"""Sumber kamera robust untuk Leviathan.

Fitur:
- Probe webcams Windows dengan 3 backend (MSMF/DSHOW/ANY) + timeout thread
- DroidCam: beberapa kandidat URL otomatis (/video, /mjpegfeed, /video.mjpeg)
- Reconnect otomatis ketika stream mati/putus
- Status yang bisa di-tampilkan di UI
"""
import os
import queue
import re
import threading
import time

import cv2

from app.core.logs import log

BACKENDS = [
    ("MSMF", cv2.CAP_MSMF),
    ("DSHOW", cv2.CAP_DSHOW),
]


def _probe_direct(index, backend_flag, timeout=3.0):
    """Buka webcam 1 frame di thread terpisah dengan timeout
    (beberapa driver block open() menit-manit).

    PENTING (anti heap-corruption native DSHOW/MSMF):
    - capture object yang sukses TIDAK di-release di sini; object cap
      dikembalikan untuk dipakai pemanggil (1 device = 1 open).
    - bila thread worker masih hidup setelah join(timeout) → tandai
      "timedout" agar pemanggil tidak langsung buka device yang sama.
    """
    result = {"frame": None, "size": None, "cap": None, "timedout": False}
    holder = {}

    def worker():
        try:
            cap = cv2.VideoCapture(index, backend_flag)
            if not cap.isOpened():
                cap.release()
                return
            try:
                # MJPG = throughput tinggi di webcam kebanyakan
                cap.set(cv2.CAP_PROP_FOURCC,
                        cv2.VideoWriter_fourcc(*"MJPG"))
                cap.set(cv2.CAP_PROP_FPS, 30)
            except Exception:
                pass
            # buang beberapa frame pertama (biasanya hitam/warm-up)
            # PENTING: JANGAN set FRAME_WIDTH/HEIGHT di sini! Pada exe
            # frozen, set resolusi di tengah capture DSHOW native
            # memicu heap-corruption (crash 0xc0000374, flaky).
            # Webcam pakai resolusi bawaan device; DroidCam yang dapat
            # 720p (backend FFmpeg, aman).
            got = None
            for _ in range(6):
                ok, f = cap.read()
                if ok and f is not None:
                    got = f
                    break
            if got is None:
                cap.release()
                return
            result["frame"] = got
            result["size"] = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                              int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            # serahkan ownership; worker jangan menyentuh cap lagi
            holder["cap"] = cap
        except Exception:
            pass

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        result["timedout"] = True
    elif "cap" in holder:
        result["cap"] = holder["cap"]
    return result if result["frame"] is not None else None


def enumerate_webcams(max_index=4):
    """Daftar kamera webcam yang hidup: [{index, backend, size}, ...]."""
    found = []
    for bname, bflag in BACKENDS:
        for idx in range(0, max_index + 1):
            r = _probe_direct(idx, bflag, timeout=2.5)
            if r is not None:
                found.append({"index": idx, "backend": bname, "size": r["size"]})
    # hapus duplikat kamera yang sama (index sama) - backend pertama (MSMF) menang
    dedup, used = [], set()
    for f in found:
        if f["index"] not in used:
            used.add(f["index"])
            dedup.append(f)
    return dedup


def droidcam_candidates(url_raw):
    """Kembangkan URL DroidCam menjadi daftar kandidat format umum."""
    base = (url_raw or "").strip()
    if not base:
        return []
    if not base.lower().startswith("http"):
        base = "http://" + base
    base = base.rstrip("/")
    cands = [base]
    m = re.match(r"https?://([^/:]+)(:\d+)?(/.*)?", base, re.IGNORECASE)
    if m:
        host, port, path = m.group(1), m.group(2) or ":4747", (m.group(3) or "")
        if not path:
            cands.append(f"http://{host}{port}/video")
        cands.append(f"http://{host}{port}/mjpegfeed?640x480")
        cands.append(f"http://{host}{port}/video.mjpeg")
        cands.append(f"http://{host}{port}/shot.jpg")
    # unik & urut
    uniq = []
    for c in cands:
        if c not in uniq:
            uniq.append(c)
    return uniq


class CameraSource:
    """Video capture threaded + reconnect + status untuk UI."""

    def __init__(self, source="webcam", index=0, url="", backend="DSHOW"):
        self.source = source            # "webcam" | "droidcam"
        self.index = str(index) if str(index).isdigit() else "0"
        self.url = url
        self.backend = (backend or "DSHOW").upper()
        self.cap = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._frame_q = queue.Queue(maxsize=2)
        self._opened_ok = False
        # status utk UI
        self.status = "IDLE"            # CONNECTING / OK / EMPTY_URL / RETRYING / FAILED
        self.status_detail = ""
        self._consec_fail = 0

    # ------------------------------------------------------------------
    def _open_webcam(self):
        order = [(self.backend,)] if self.backend in ("MSMF", "DSHOW", "ANY") \
            else [(n,) for n, _ in BACKENDS]
        back_list = []
        for (b,) in order:
            flag = dict(BACKENDS)[b]
            back_list.append((b, flag))
        # kalo backend pilihan gagal, coba sisanya
        if self.backend in ("MSMF", "DSHOW", "ANY"):
            for name, flag in BACKENDS:
                if name != self.backend:
                    back_list.append((name, flag))
        idx = int(self.index)
        for bname, flag in back_list:
            self.status = "CONNECTING"
            self.status_detail = f"webcam #{idx} [{bname}]"
            r = _probe_direct(idx, flag, timeout=2.8)
            if r is not None:
                # pakai capture object hasil probe — jangan buka dua kali!
                cap = r.get("cap")
                if cap.isOpened():
                    try:
                        cap.set(cv2.CAP_PROP_FOURCC,
                                cv2.VideoWriter_fourcc(*"MJPG"))
                        cap.set(cv2.CAP_PROP_FPS, 30)
                    except Exception:
                        pass
                if cap.isOpened() and self.cap is None:
                    self.cap = cap
                    self._opened_ok = True
                    self.status = "OK"
                    self.status_detail = f"webcam #{idx} [{bname}] {r['size'][0]}x{r['size'][1]}"
                    log("kamera webcam OK: " + self.status_detail)
                    return True
                elif cap.isOpened() and self.cap is not None:
                    cap.release()      # probe dobel — buang yang ini
            if r is None or r.get("timedout"):
                # thread probe lama mungkin MASIH memegang device ini.
                # JANGAN pernah buka device yang sama lagi (backend lain
                # pun tidak) — double-open DSHOW = heap corruption crash.
                # Gagal bersih → retry timer akan mencoba lagi nanti.
                log(f"probe webcam [{bname}] timeout - skip semua backend "
                    "(anti double-open)")
                self.status = "FAILED"
                self.status_detail = f"webcam #{idx} [{bname}] timeout"
                return False
        self.status = "FAILED"
        self.status_detail = "tidak ada webcam yang terdeteksi"
        log("kamera webcam GAGAL: " + self.status_detail)
        return False

    def _open_droidcam(self):
        cands = droidcam_candidates(self.url)
        for u in cands:
            self.status = "CONNECTING"
            self.status_detail = u
            cap = cv2.VideoCapture(u)
            try:
                # DroidCam mendukung HD - minta 720p agar teks/jenis ikan jelas
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            except Exception:
                pass
            got = False
            t_end = time.time() + 6.0
            while time.time() < t_end:
                ok, f = cap.read()
                if ok and f is not None:
                    got = True
                    break
            if got:
                self.cap = cap
                self._opened_ok = True
                self.status = "OK"
                self.status_detail = u
                log(f"kamera DroidCam OK: {u}")
                return True
            cap.release()
        self.status = "FAILED"
        self.status_detail = (f"DroidCam tidak terhubung ({len(cands)} URL dicoba). "
                              "Cek IP:port dan pastikan app DroidCam jalan di HP.")
        log("kamera DroidCam GAGAL: " + self.status_detail)
        return False

    def open(self):
        if self.source == "droidcam" and self.url:
            return self._open_droidcam()
        if self.source == "auto":
            # AUTO: webcam dulu; gagal → DroidCam
            if self._open_webcam():
                return True
            if self.url:
                return self._open_droidcam()
            return False
        return self._open_webcam()

    # ------------------------------------------------------------------
    def start(self):
        if self.source == "droidcam" and not (self.url or "").strip():
            self.status = "EMPTY_URL"
            self.status_detail = "URL DroidCam belum diisi (Panel Admin ▸ SISTEM)"
            return False
        ok = self.open()
        if not ok:
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def _loop(self):
        while self._running:
            ok, frame = False, None
            with self._lock:
                if self.cap is not None:
                    try:
                        ok, frame = self.cap.read()
                    except Exception:
                        ok, frame = False, None
            if ok and frame is not None:
                self._frame_q.put(frame) if not self._frame_q.full() else None
                self._consec_fail = 0
            else:
                self._consec_fail += 1
                # setelah ±12 frame gagal (±1-2 dtk) → coba sambung ulang
                if self._consec_fail >= 12:
                    self._consec_fail = 0
                    self.status = "RETRYING"
                    with self._lock:
                        try:
                            if self.cap is not None:
                                self.cap.release()
                        except Exception:
                            pass
                        self.cap = None
                    self._opened_ok = False
                    time.sleep(0.8)
                    try:
                        self.open()
                    except Exception as e:
                        # jangan biarkan thread kamera mati diam-diam
                        log("kamera thread error saat reconnect: %r" % (e,))
                        self.status = "FAILED"
                        time.sleep(2.0)

    # ------------------------------------------------------------------
    def read(self):
        try:
            return self._frame_q.get_nowait()
        except queue.Empty:
            return None

    def is_open(self):
        return self._opened_ok

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.5)
        with self._lock:
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
        self._opened_ok = False
        self.status = "IDLE"
