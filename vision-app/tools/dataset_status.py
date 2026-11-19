"""Cek status dataset Leviathan.

Pakai:
  python tools\\dataset_status.py            -> buat folder yang hilang + laporkan
  python tools\\dataset_status.py --init     -> (sama, buat folder bila belum ada)

Menampilkan jumlah foto per jenis dan kesiapan menuju target minimum pameran.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import BASE_DIR  # noqa: E402

DATASETS = os.path.join(BASE_DIR, "datasets")
TARGET = {
    "guppy":    150,
    "koi":      200,
    "cupang":   100,
    "molly":    100,
    "komet":    200,
    "chana":     80,
    "arwana":    80,
    "ikan_mas": 200,
}
EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def count_images(folder):
    if not os.path.isdir(folder):
        return 0
    return sum(1 for f in os.listdir(folder)
               if f.lower().endswith(EXTS))


def main():
    do_init = "--init" in " ".join(sys.argv[1:]) or not os.path.isdir(DATASETS)
    rows = []
    for cls, target in TARGET.items():
        folder = os.path.join(DATASETS, cls)
        if do_init and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
            print(f"  [buat] {folder}")
        n = count_images(folder)
        rows.append((cls, n, target))
    total = 0
    ok_n = 0
    print()
    print("=== STATUS DATASET LEVIATHAN ===")
    for cls, n, target in rows:
        pct = min(100, int(n * 100 / target)) if target else 0
        mark = "OK " if n >= target else ("~  " if n > 0 else "!! ")
        bar = "#" * (pct // 5) + "." * (20 - pct // 5)
        print(f"  {mark}{cls:9s} {n:5d}/{target:<4d} |{bar}| {pct:3d}%")
        total += n
        ok_n += 1 if n >= target else 0
    print("-" * 44)
    print(f"  TOTAL FOTO: {total}   JENIS CAPAI TARGET: {ok_n}/8")
    if ok_n == 8:
        print("  >>> SIAP DI-UPLOAD ke Roboflow utk labeling")
    else:
        missing = [c for c, n, t in rows if n < t]
        print("  >>> Yang masih kurang: " + ", ".join(missing))
    print()
    print("Folder dataset: " + DATASETS)


if __name__ == "__main__":
    main()
