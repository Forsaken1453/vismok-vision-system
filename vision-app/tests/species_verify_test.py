# -*- coding: utf-8 -*-
"""Uji verifikasi spesies dgn YOLO-World open-vocabulary:
foto per folder harus terdeteksi sebagai jenis yang sesuai folder.
"""
import glob
import os
import sys

sys.path.insert(0, r"D:\Leviathan")
from ultralytics import YOLO

# prompt per kelas folder (bahasa Inggris spesifik)
SPECIES = {
    "guppy": "guppy fish",
    "koi": "koi carp",
    "cupang": "betta fish",
    "molly": "molly fish",
    "komet": "goldfish",
    "chana": "snakehead fish",
    "arwana": "arowana fish",
    "ikan_mas": "carp fish",
}

m = YOLO("yolov8s-worldv2.pt")
m.set_classes(list(SPECIES.values()))
names = list(SPECIES.keys())

total = 0
match = 0
for ci, (cls, prompt) in enumerate(SPECIES.items()):
    imgs = sorted(glob.glob(rf"D:\Leviathan\datasets\{cls}\*.jpg"))
    sample = imgs[::max(1, len(imgs) // 6)][:6]
    hits = 0
    for p in sample:
        r = m.predict(p, conf=0.20, verbose=False, device=0)[0]
        if r.boxes is None or len(r.boxes) == 0:
            pred = "-"
        else:
            pred = names[int(r.boxes.cls[0].cpu().item())]
        total += 1
        ok = (pred == cls)
        match += ok
        hits += ok
        print(f"  {cls:9s} -> {pred:9s} {'OK' if ok else 'X'}")
    print(f"[{cls}] {hits}/{len(sample)}")
print(f"\nMATCH TOTAL: {match}/{total}")
