"""LEVIATHAN - Asisten Vision Pakan Ikan

Entry point aplikasi. Jalankan: python run.py
"""
import os
import sys


def _install_crash_logging():
    """Exception Python yang lolos → tulis ke data\leviathan.log."""
    import traceback

    def hook(t, v, tb):
        try:
            from app.core.logs import log
            log("FATAL EXCEPTION:\n" + "".join(
                traceback.format_exception(t, v, tb)))
        except Exception:
            pass
        sys.__excepthook__(t, v, tb)
    sys.excepthook = hook


def main():
    _install_crash_logging()
    from PySide6.QtWidgets import QApplication

    from app.config import ensure_dirs
    from app.core.database import init_db

    ensure_dirs()
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("Vismok Aseli Ngawi")
    app.setStyle("Fusion")

    # ikon aplikasi (taskbar & titlebar)
    from PySide6.QtGui import QIcon
    from app.config import BASE_DIR
    icon_png = os.path.join(BASE_DIR, "assets", "img", "app_icon_1024.png")
    if os.path.exists(icon_png):
        app.setWindowIcon(QIcon(icon_png))

    # muat font bawaan SEBELUM theme/QR ditranslate agar family benar
    from app.ui.fonts import load_fonts
    load_fonts()

    from app.ui.main_window import MainWindow

    window = MainWindow()
    window.showFullScreen()   # mode kiosk untuk toko/pameran
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
