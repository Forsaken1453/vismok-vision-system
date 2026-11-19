# -*- coding: utf-8 -*-
"""Uji detektor ONNX app: foto wajah manusia TIDAK boleh kedeteksi."""
import os
import sys

sys.path.insert(0, r"D:\Leviathan")
import cv2

from app.core.detector import YoloOnnxDetector

det = YoloOnnxDetector(r"D:\Leviathan\models\model.onnx")
p = r"D:\Leviathan\datasets\_face_test.jpg"
frame = cv2.imread(p)
dets, fps = det.detect(frame)
if not dets:
    print("WAJAH MANUSIA: TIDAK ADA DETEKSI (benar - tidak menyerupai ikan)")
else:
    for d in dets:
        print("WAJAH MANUSIA: SALAH ->", d["class_name"], d["conf"])
os.remove(p)
