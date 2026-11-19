# -*- coding: utf-8 -*-
"""Set camera_source di DB dev."""
import sqlite3
import sys

val = sys.argv[1] if len(sys.argv) > 1 else "auto"
con = sqlite3.connect(r"D:\Leviathan\data\leviathan.db")
cur = con.cursor()
cur.execute("SELECT key FROM config WHERE key='camera_source'")
if cur.fetchone():
    cur.execute("UPDATE config SET value=? WHERE key='camera_source'", (val,))
else:
    cur.execute("INSERT INTO config(key,value) VALUES(?,?)",
                ("camera_source", val))
con.commit()
print("dev camera_source =", val)
con.close()
