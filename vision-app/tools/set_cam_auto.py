import sqlite3
c = sqlite3.connect(r"D:\Leviathan\data\leviathan.db")
c.execute("UPDATE config SET value='auto' WHERE key='camera_source'")
c.commit()
print("camera_source ->", c.execute(
    "SELECT value FROM config WHERE key='camera_source'").fetchone()[0])
c.close()
