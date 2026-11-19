"""Konfigurasi & path Leviathan."""
import os
import sys

# Root = folder tempat run.py berada (juga saat dibekukan PyInstaller)
def _base_dir():
    if getattr(sys, "frozen", False):                 # jalan sebagai .exe
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = _base_dir()

DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
SNAP_DIR = os.path.join(DATA_DIR, "snapshots")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
DB_PATH = os.path.join(DATA_DIR, "leviathan.db")
MODEL_PATH = os.path.join(MODELS_DIR, "model.onnx")
CLASSES_PATH = os.path.join(MODELS_DIR, "classes.json")

# Default kamera / deteksi (di-override dari tabel config via Admin Panel)
DEFAULTS = {
    "camera_source": "auto",            # auto (webcam dulu → droidcam) | webcam | droidcam
    "camera_index": "0",
    "camera_backend": "DSHOW",          # MSMF | DSHOW | ANY
    "droidcam_url": "http://192.168.1.10:4747/video",
    "conf_threshold": "0.55",
    "admin_pin": "2026",
    "store_name": "Toko Ikan Aseli Ngawi",
    "imgsz": "640",
}


def ensure_dirs():
    for d in (DATA_DIR, MODELS_DIR, SNAP_DIR, EXPORT_DIR):
        os.makedirs(d, exist_ok=True)
