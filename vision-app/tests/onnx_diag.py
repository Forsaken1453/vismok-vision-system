# -*- coding: utf-8 -*-
"""Diagnosa output mentah model ONNX: apakah sudah mengandung sigmoid?"""
import sys

sys.path.insert(0, r"D:\Leviathan")
import cv2
import numpy as np
import onnxruntime as ort

sess = ort.InferenceSession(r"D:\Leviathan\models\model.onnx", providers=["CPUExecutionProvider"])
inp = sess.get_inputs()[0].name
print("input:", inp, sess.get_inputs()[0].shape)

for path, label in [
    (r"D:\Leviathan\datasets\export\images\valid\koi_00001.jpg", "KOI"),
    (r"D:\Leviathan\datasets\export\images\valid\chana_00001.jpg", "CHANA"),
]:
    if not __import__("os").path.exists(path):
        # ambil file valid pertama kelas itu
        import glob
        cands = glob.glob(rf"D:\Leviathan\datasets\export\images\valid\{label.lower()}_*.jpg")
        if not cands:
            print(label, ": tidak ada gambar")
            continue
        path = cands[0]
    img = cv2.imread(path)
    img = cv2.resize(img, (640, 640))
    arr = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    arr = arr.transpose(2, 0, 1)[None]
    out = sess.run(None, {inp: arr})[0]
    p = out[0]
    if p.shape[0] < p.shape[1]:
        p = p.T
    cls = p[:, 4:]
    print(f"{label}: output {out.shape}, cls min={cls.min():.4f} max={cls.max():.4f} "
          f"ada negatif={bool((cls < 0).any())}")
