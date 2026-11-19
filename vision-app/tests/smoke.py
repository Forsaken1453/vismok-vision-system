"""Smoke test Leviathan (offscreen): DB, pages, deteksi demo, build-exe sanity."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from app.config import ensure_dirs
from app.core.database import init_db, species_all, recs_for_species

ensure_dirs()
init_db()

app = QApplication(sys.argv)
from app.ui.fonts import load_fonts
load_fonts()

from app.ui.main_window import MainWindow

w = MainWindow()
w.show()

results = []

def step1():
    sp = species_all()
    assert len(sp) == 8, f"species = {len(sp)}"
    recs = recs_for_species(sp[0]["id"])
    assert recs, "rekomendasi kosong"
    results.append(f"DB OK: {len(sp)} species, rekomendasi contoh: {recs[0]['nama']}")
    print(results[-1], flush=True)

def step2():
    sp = species_all()[1]
    w.select_manual(sp)
    results.append(f"Result page OK: {sp['display_name']}")
    print(results[-1], flush=True)
    w.page_detail.set_species(sp); w.go_page("detail")
    results.append("Detail page OK"); print(results[-1], flush=True)
    w.go_page("manual"); results.append("Manual OK (grid %d)" % w.page_manual.grid.count())
    print(results[-1], flush=True)
    w.go_page("library"); results.append("Library OK (grid %d)" % w.page_library.grid.count())
    print(results[-1], flush=True)
    w.go_page("history"); results.append("History page OK (%d baris)" % w.page_history.tbl.rowCount())
    print(results[-1], flush=True)
    w.go_page("catalog"); results.append("Catalog OK")
    print(results[-1], flush=True)
    w.go_page("kamera"); results.append("Back kamera OK"); print(results[-1], flush=True)

def step3():
    for _ in range(240):
        w._loop()
    results.append("Loop deteksi OK (model=%s, HUD situs %s)" % (getattr(w.detector, "name", "?"), w.page_standby.det_panel.isVisible()))
    print(results[-1], flush=True)
    # riwayat → insert manual & reload
    from app.core.database import add_detection, detections_list
    add_detection("guppy", 0.91, "")
    assert len(detections_list()) >= 1
    w.page_history.reload()
    results.append("Riwayat OK (%d baris)" % w.page_history.tbl.rowCount())
    print(results[-1], flush=True)
    results.append("ALL TESTS PASSED")
    print("ALL TESTS PASSED", flush=True)
    w.close()
    app.quit()

QTimer.singleShot(120, lambda: (step1(), step2(), step3()))
app.exec()
