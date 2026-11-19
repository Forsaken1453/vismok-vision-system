"""Pemuatan font bawaan + pemilihan nama family yg tersedia."""
import os

from PySide6.QtGui import QFontDatabase

from app.config import BASE_DIR

FONTS_DIR = os.path.join(BASE_DIR, "assets", "fonts")

# hasil update setelah load_fonts()
FAMILY = {
    "display": "Rajdhani",   # jatuh ke ini bila Orbitron gagal termuat
    "body": "Segoe UI",      # di-update jadi "Inter" kalau font termuat
}

# font display premium: Orbitron > Rajdhani (fallback)
_DISPLAY_PREFS = ("Orbitron", "Rajdhani")


def load_fonts():
    """Termuat semua .ttf di assets/fonts. Return list nama family baru."""
    loaded = []
    if not os.path.isdir(FONTS_DIR):
        return loaded
    for fn in sorted(os.listdir(FONTS_DIR)):
        if not fn.lower().endswith((".ttf", ".otf")):
            continue
        fid = QFontDatabase.addApplicationFont(os.path.join(FONTS_DIR, fn))
        if fid < 0:
            continue
        fams = QFontDatabase.applicationFontFamilies(fid)
        for f in fams:
            if f not in loaded:
                loaded.append(f)
    fams_all = set(QFontDatabase.families())

    # pilih font display futuristik terbaik yg tersedia
    for cand in _DISPLAY_PREFS:
        if cand in fams_all:
            FAMILY["display"] = cand
            break

    # pilih body font: Inter kalau tersedia, else Segoe UI
    for cand in ("Inter", "Inter Regular"):
        if cand in fams_all:
            FAMILY["body"] = cand
            break
    # nama variable font kadang muncul dgn nama lain — cari prefix Inter
    if FAMILY["body"] == "Segoe UI":
        for f in sorted(fams_all):
            if f.startswith("Inter"):
                FAMILY["body"] = f
                break
    return loaded
