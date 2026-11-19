import os, sys, traceback
os.environ["QT_QPA_PLATFORM"] = "offscreen"
BASE = r"D:\Leviathan"
sys.path.insert(0, BASE)
os.chdir(BASE)

from PySide6.QtWidgets import QApplication
from app.config import ensure_dirs
from app.core.database import init_db
ensure_dirs(); init_db()
app = QApplication(sys.argv)
from app.ui.fonts import load_fonts
load_fonts()
from app.ui.main_window import MainWindow
try:
    w = MainWindow()
    print("INIT OK", flush=True)
except Exception:
    traceback.print_exc()
