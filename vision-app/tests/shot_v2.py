import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"D:\Leviathan"); os.chdir(r"D:\Leviathan")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
app = QApplication(sys.argv)
from app.ui.fonts import load_fonts
load_fonts()
from app.config import ensure_dirs
from app.core.database import init_db
ensure_dirs(); init_db()
from app.ui.main_window import MainWindow

w = MainWindow(); w.resize(1600, 900); w.show()
out = []

def s1():  # hasil deteksi + foto referensi ikan
    sp = next((x for x in w.species if x["class_name"] == "arwana"),
              None) or w.species[6]
    w.page_result.set_result(sp, None, 0.87)
    w.go_page("result")
    w.grab().save(r"D:\Leviathan\tests\shots\10_vismok_result.png")
    out.append("result OK")

def s2():  # detail ikan
    w.show_detail(w.page_result._species)
    w.grab().save(r"D:\Leviathan\tests\shots\11_vismok_detail.png")
    out.append("detail OK")

def s3():  # katalog pakan + foto produk
    w.go_page("catalog")
    w.grab().save(r"D:\Leviathan\tests\shots\12_vismok_catalog.png")
    out.append("catalog OK")

def s4():  # halaman kamera + mode manual
    w.go_page("standby")
    w.page_standby.update_hud([], fps=21, model="DEMO", threshold="0.55")
    w.page_standby.chip_cam.set_ok(True, "KAMERA: OK #0 [DSHOW] 640x480")
    w.page_standby.chip_status.setText("● SCANNING")
    w._on_mode_picked("manual")
    def s5():
        w.grab().save(r"D:\Leviathan\tests\shots\13_vismok_manual.png")
        out.append("manual OK")
        app.quit()
    QTimer.singleShot(500, s5)

QTimer.singleShot(500, s1)
QTimer.singleShot(900, s2)
QTimer.singleShot(1300, s3)
QTimer.singleShot(1700, s4)
app.exec()
print(" | ".join(out))
