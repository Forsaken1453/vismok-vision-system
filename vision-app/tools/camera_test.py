"""ALAT DIAGNOSA KAMERA Leviathan — simpan foto tes & tampilkan status tiap backend.

Pemakaian (dari folder D:\\Leviathan):
    python tools\\camera_test.py            # scan + tes + simpan foto ke data\\cam_test
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

OUT_DIR = os.path.join("data", "cam_test")


def test_one(idx, backend_name, backend_flag):
    t0 = time.time()
    cap = cv2.VideoCapture(idx, backend_flag)
    ok_open = cap.isOpened()
    got, frame = cap.read()
    has_frame = got and (frame is not None) and getattr(frame, "size", 0) > 0
    took = time.time() - t0
    size = None if frame is None else f"{frame.shape[1]}x{frame.shape[0]}"
    result = {"backend": backend_name, "index": idx, "open": ok_open,
              "frame": has_frame, "size": size, "took": round(took, 1)}
    if has_frame:
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, f"cam_{backend_name}_{idx}.jpg")
        cv2.imwrite(path, frame)
        result["saved"] = path
    cap.release()
    return result


def main():
    print()
    print("== LEVIATHAN CAMERA TEST ==")
    print(f"OpenCV: {cv2.__version__}")
    print("-" * 60)

    working = []
    for name, flag in [("MSMF", cv2.CAP_MSMF), ("DSHOW", cv2.CAP_DSHOW),
                       ("ANY", cv2.CAP_ANY)]:
        for idx in range(3):
            r = test_one(idx, name, flag)
            mark = "✔ HIDUP" if r["frame"] else "✖"
            line = (f"[{mark}] backend={r['backend']:5} index={r['index']} "
                    f"open={r['open']} frame={r['frame']} size={r['size']} "
                    f"({r['took']}s)")
            print(line)
            if r["frame"]:
                working.append(r)
                if "saved" in r:
                    print(f"        foto tes disimpan: {r['saved']}")

    print("-" * 60)
    if working:
        w = working[0]
        print(f"✔ KAMERA SIAP: {w['backend']} index {w['index']}")
        print(f"  Di Leviathan: Panel Admin ▸ SISTEM ▸ SUMBER KAMERA: Webcam ▸ "
              f"deteksi → pilih \"{w['backend']}  #{w['index']}\"")
    else:
        print("✖ SEMUA KAMERA GAGAL. Cek:")
        print("  1. Device Manager ▸ Cameras ▸ 'Integrated Camera' — Status harus OK "
              "(kalau Error/disabled → klik kanan ▸ Enable device)")
        print("  2. Windows Settings ▸ Privacy & Security ▸ Camera ▸ "
              "'Let desktop apps access your camera' = ON")
        print("  3. Tombol fisik kamera (Fn+F9 di Lenovo) — pastikan tidak ter-mute")
    print()


if __name__ == "__main__":
    main()
