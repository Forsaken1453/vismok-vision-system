# -*- coding: utf-8 -*-
"""Screenshot standby saat kamera TIDAK konek (droidcam IP invalid)."""
import os, sys

os.chdir(r"D:\Leviathan")
sys.path.insert(0, r"D:\Leviathan")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

app = QApplication([])

from app.core import database as db
from app.core.database import get_conn, set_config
db.init_db()
conn = get_conn()
set_config(conn, "droidcam_url", "http://192.168.99.99:4747/video")
set_config(conn, "camera_source", "droidcam")
conn.close()

from app.ui.main_window import MainWindow
w = MainWindow()
w.resize(1700, 900)
w.show()

shots = []


def grab(tag):
    img = w.grab()
    fn = rf"tests\shots\19_nocam_{tag}.png"
    img.save(fn)
    shots.append(fn)
    print("shot", tag, "cam status:", getattr(w.camera_source, "status", None),
          "detail:", getattr(w.camera_source, "status_detail", ""))


QTimer.singleShot(4000, lambda: grab("a"))
QTimer.singleShot(7000, lambda: grab("b"))
QTimer.singleShot(12000, lambda: grab("c"))
QTimer.singleShot(13000, app.quit)
app.exec()
