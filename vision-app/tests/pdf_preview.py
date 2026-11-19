# -*- coding: utf-8 -*-
"""Preview PDF kwitansi dengan font Orbitron dimuat (mirip kondisi exe)."""
import os, sys

os.chdir(r"D:\Leviathan")
sys.path.insert(0, r"D:\Leviathan")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor, QFontDatabase

app = QApplication([])
for f in os.listdir(r"assets\fonts"):
    QFontDatabase.addApplicationFont(os.path.join(r"assets\fonts", f))
print("fonts loaded")

from app.core import database as db
db.init_db()
sp = [s for s in db.species_all() if s["class_name"] == "komet"][0]
recs = db.recs_for_species(sp["id"])
items = [dict(r, qty=q) for r, q in zip(recs[:4], [2, 1, 3, 1])]
tips = sp.get("tips") or [
    "Tips 1 panjang untuk pembungkus baris ganda kalau teks terlalu "
    "panjang untuk satu baris kwitansi.",
    "Beri pakan 2x sehari.",
]

from app.core.pdf_export import export_receipt
img = QImage(874, 1240, QImage.Format_RGB32)
img.fill(QColor("white"))
export_receipt(sp, 0.76, items, tips, "VISMOK ASELI NGAWI",
               snapshot_path=r"assets\img\fish\komet.jpg", device=img)
img.save(r"tests\shots\18_pdf_orbitron.png")
print("saved, items:", len(items))
