# -*- coding: utf-8 -*-
"""Uji detektor ONNX app (post sigmoid-fix):
1) foto wajah manusia TIDAK boleh kedeteksi
2) akurasi sampel validasi per kelas
"""
import glob
import os
import random
import sys

sys.path.insert(0, r"D:\Leviathan")
sys.path.insert(0, r"D:\Leviathan\tools")
import cv2

from app.core.detector import YoloOnnxDetector
import collect_dataset as c

det = YoloOnnxDetector(r"D:\Leviathan\models\model.onnx")

# --- 1. uji wajah ---
items = c.api_search("woman face portrait photograph", limit=3)
p = r"D:\Leviathan\datasets\_face_test.jpg"
c.download((items[0]["url"], p))
frame = cv2.imread(p)
dets, fps = det.detect(frame)
if not dets:
    print("WAJAH: TIDAK ADA DETEKSI (BENAR)")
else:
    print(f"WAJAH: {len(dets)} deteksi (SALAH) ->",
          [(d["class_name"], d["conf"]) for d in dets[:5]])
os.remove(p)

# --- 2. akurasi sampel valid ---
random.seed(7)
ok = 0
tot = 0
for cls in ["guppy", "koi", "cupang", "molly", "komet",
            "chana", "arwana", "ikan_mas"]:
    imgs = glob.glob(rf"D:\Leviathan\datasets\export\images\valid\{cls}_*.jpg")
    sample = random.sample(imgs, min(5, len(imgs)))
    for ip in sample:
        dts, _ = det.detect(cv2.imread(ip))
        pred = dts[0]["class_name"] if dts else "(kosong)"
        cf = dts[0]["conf"] if dts else 0
        ok += (pred == cls)
        tot += 1
        mark = "OK " if pred == cls else "X  "
        print(f"  {mark} {cls:9s} -> {pred:9s} {cf:.2f}")
print(f"AKURASI SAMPEL: {ok}/{tot}")
