# -*- coding: utf-8 -*-
"""Set camera_source di DB dist (isolasi crash test)."""
import sqlite3

con = sqlite3.connect(r"D:\Leviathan\dist\VISMOK\data\leviathan.db")
cur = con.cursor()
cur.execute("SELECT key FROM config WHERE key='camera_source'")
if cur.fetchone():
    cur.execute("UPDATE config SET value=? WHERE key='camera_source'", ("none",))
else:
    cur.execute("INSERT INTO config(key,value) VALUES(?,?)",
                ("camera_source", "none"))
con.commit()
print("rows:", list(cur.execute(
    "SELECT key,value FROM config WHERE key='camera_source'")))
con.close()
