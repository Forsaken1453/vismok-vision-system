"""Set nama toko di DB (dev + dist)."""
import os
import sys

sys.path.insert(0, r"D:\Leviathan")
NAMA = "Toko Ikan Aseli Ngawi"


def set_store(db_path):
    import sqlite3
    if not os.path.exists(db_path):
        return "skip (belum ada)"
    c = sqlite3.connect(db_path)
    c.execute("UPDATE config SET value=? WHERE key='store_name'", (NAMA,))
    c.commit()
    val = c.execute("SELECT value FROM config WHERE key='store_name'").fetchone()
    c.close()
    return val[0] if val else "(kosong)"


print("dev :", set_store(r"D:\Leviathan\data\leviathan.db"))
print("dist:", set_store(r"D:\Leviathan\dist\VISMOK\data\leviathan.db"))
