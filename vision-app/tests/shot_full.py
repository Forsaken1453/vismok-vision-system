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
from app.core.database import init_db
ensure_dirs(); init_db()
from app.ui.main_window import MainWindow

w = MainWindow()
w.resize(1600, 900)
w.show()

OUT = r"D:\Leviathan\tests\shots"

def snap1():
    def fill():
        w.page_standby.update_hud([
            {"class_name": "guppy", "conf": 0.91, "box": [100, 100, 300, 250]},
            {"class_name": "komet", "conf": 0.64, "box": [500, 200, 700, 320]},
        ], fps=22, model="ONNX", threshold="0.55", snaps=None)
        w.page_standby.chip_cam.set_ok(True, "KAMERA: OK #0 [DSHOW] 640x480")
        w.page_standby.chip_fps.set_ok(True, "FPS: 22")
    fill()
    QTimer.singleShot(400, lambda: (w.grab().save(os.path.join(OUT, "06_full_kamera.png")),
                                     print("saved full", flush=True)))
    QTimer.singleShot(900, app.quit)

QTimer.singleShot(500, snap1)
app.exec()
print("DONE", flush=True)
