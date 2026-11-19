"""Helper log ringan ke file (penting untuk exe no-console)."""
import os
import time


def log(msg):
    try:
        from app.config import DATA_DIR
        os.makedirs(DATA_DIR, exist_ok=True)
        path = os.path.join(DATA_DIR, "leviathan.log")
        line = time.strftime("[%Y-%m-%d %H:%M:%S] ") + str(msg) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
