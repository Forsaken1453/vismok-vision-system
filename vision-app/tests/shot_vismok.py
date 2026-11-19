import os, sys, sqlite3
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

def fill():
    w.page_standby.update_hud([], fps=21, model="DEMO", threshold="0.55")
    w.page_standby.chip_cam.set_ok(True, "KAMERA: OK #0 [DSHOW] 640x480")
    w.page_standby.chip_status.setText("● SCANNING")

def shot():
    w.grab().save(r"D:\Leviathan\tests\shots\09_vismok_scan.png")
    print("saved scan", flush=True)
    w._on_source_picked("droidcam")
    QTimer.singleShot(300, check)

def check():
    c = sqlite3.connect(r"D:\Leviathan\data\leviathan.db")
    val = c.execute("SELECT value FROM config WHERE key='camera_source'").fetchone()[0]
    c.close()
    print("switch droidcam OK ->", val, flush=True)
    app.quit()

QTimer.singleShot(600, fill)
QTimer.singleShot(1000, shot)
app.exec()
print("DONE", flush=True)
