import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"D:\Leviathan")
os.chdir(r"D:\Leviathan")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

app = QApplication(sys.argv)
from app.ui.fonts import load_fonts
load_fonts()

from app.config import ensure_dirs
from app.core.database import init_db, species_all
ensure_dirs(); init_db()
from app.ui.main_window import MainWindow

w = MainWindow()
w.resize(1600, 900)
w.show()

OUT = os.path.join(w.BASE_DIR_test if hasattr(w, "BASE_DIR_test") else r"D:\Leviathan\tests", "shots")
os.makedirs(OUT, exist_ok=True)

sp = species_all()[2]

def g(page, name, extra=None):
    def do():
        w.go_page(page)
        if extra:
            extra()
        QTimer.singleShot(250, lambda: save(name, page))
    return do

def save(name, page):
    if page == "kamera":
        w.page_standby.grab().save(os.path.join(OUT, name + ".png"))
    else:
        w.pages.grab().save(os.path.join(OUT, name + ".png"))
    print("saved", name, flush=True)

# simulate deteksi demo untuk HUD
def hud_fill():
    w.page_standby.update_hud([
        {"class_name": "guppy", "conf": 0.91, "box": [100, 100, 300, 250]},
        {"class_name": "komet", "conf": 0.64, "box": [400, 200, 600, 320]},
    ], fps=22, model="DEMO", threshold="0.55", snaps=None)

def do_all():
    print("MARK: kamera", flush=True)
    w.go_page("kamera"); hud_fill()
    QTimer.singleShot(300, lambda: (w.page_standby.grab().save(os.path.join(OUT, "01_kamera.png")), print("saved kamera", flush=True)))
    print("MARK: history", flush=True)
    QTimer.singleShot(700, lambda: g("history", "02_riwayat", lambda: w.page_history.reload())())
    print("MARK: catalog", flush=True)
    QTimer.singleShot(1200, lambda: g("catalog", "03_katalog")())
    print("MARK: library", flush=True)
    QTimer.singleShot(1600, lambda: g("library", "04_panduan")())
    print("MARK: result", flush=True)
    QTimer.singleShot(2000, lambda: g("result", "05_hasil", lambda: w.page_result.set_result(sp, None, conf=0.93))())
    QTimer.singleShot(2400, lambda: app.quit())
    print("MARK: scheduled", flush=True)

# deep chroma: insert snapshot fake ke history agar tampil
from app.core.database import add_detection
add_detection("guppy", 0.91, ""); add_detection("koi", 0.78, ""); add_detection("arwana", 0.66, "")

QTimer.singleShot(600, do_all)
app.exec()
print("SHOTS DONE", flush=True)
