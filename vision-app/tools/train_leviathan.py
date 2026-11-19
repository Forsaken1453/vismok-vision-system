"""Training YOLOv11n untuk Leviathan (RTX 3050, 6GB).

Prasyarat:
  1. Dataset hasil EXPORT Roboflow (format YOLOv8/YOLOv11 Object Detection),
     diekstrak di D:\Leviathan\datasets\export\
     (isinya: train/ valid/ test/ + data.yaml)
  2. PyTorch CUDA + ultralytics sudah ter-install

Pakai:
  python tools\\train_leviathan.py                 # default settings
  python tools\\train_leviathan.py --epochs 150   # latih lebih lama

Hasil:
  - model terbaik  : runs\\detect\\leviathan_y11n\\weights\\best.pt
  - ONNX           : dipasang otomatis ke models\\model.onnx (dev) dan
                     dist\\Leviathan\\models\\model.onnx (+ classes.json)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA = os.path.join(BASE, "datasets", "export", "data.yaml")
RUN_DIR = os.path.join(BASE, "runs")
MODEL_OUT = os.path.join(BASE, "models")


def check_env():
    try:
        import torch
    except ImportError:
        print("!! PyTorch belum ter-install. Jalankan:")
        print("   python -m pip install torch torchvision --index-url "
              "https://download.pytorch.org/whl/cu121")
        return False
    cuda = torch.cuda.is_available()
    print(f"PyTorch {torch.__version__} | CUDA: {cuda}"
          + (f" | GPU: {torch.cuda.get_device_name(0)}" if cuda else
             "  (akan training di CPU - LAMBAT!)"))
    try:
        import ultralytics  # noqa: F401
    except ImportError:
        print("!! ultralytics belum ter-install: python -m pip install ultralytics")
        return False
    return True


def check_data(path):
    if not os.path.exists(path):
        print("!! data.yaml tidak ditemukan:", path)
        print("   1. Export dari Roboflow (format YOLOv8/YOLOv11)")
        print("   2. Ekstrak zip ke D:\\Leviathan\\datasets\\export\\")
        print("      (harus ada folder train/ valid/ test/ + data.yaml)")
        print("   Atau pakai: python tools\\train_leviathan.py "
              "--data path\\ke\\data.yaml")
        return False
    names = read_names(path)
    print(f"Data OK: {path}")
    print("Kelas :", ", ".join(names))
    return True


def read_names(data_yaml):
    """Ambil daftar nama kelas dari data.yaml tanpa pyyaml."""
    try:
        import yaml
        return list(yaml.safe_load(open(data_yaml, "r", encoding="utf-8"))["names"].values())
    except Exception:
        pass
    # fallback parser manual (blok names: 0: xxx \n 1: yyy ...)
    names = []
    in_names = False
    with open(data_yaml, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("names:"):
                in_names = True
                if "[" in line:                    # names: [a, b, c]
                    inner = line.split("[", 1)[1].split("]")[0]
                    return [x.strip() for x in inner.split(",") if x.strip()]
                continue
            if in_names:
                s = line.strip()
                if ":" in s:
                    names.append(s.split(":", 1)[1].strip())
                elif s and not s.startswith("-"):
                    in_names = s and in_names and not s[0].isdigit()
                    if not in_names:
                        break
                elif s.startswith("- "):
                    names.append(s[2:].strip())
    return names


def train(epochs, imgsz, batch, data, model_name="yolo11n.pt",
          run_name="leviathan_y11n"):
    """Latih YOLO langsung via API Python (CLI '-m ultralytics'
    tidak tersedia di install ini)."""
    import torch
    from ultralytics import YOLO

    print(f"GPU tersedia: {torch.cuda.is_available()} "
          f"({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'})")
    model = YOLO(model_name)            # auto-download saat pertama kali
    results = model.train(
        data=data,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=0,
        workers=4,
        name=run_name,
        exist_ok=True,
        project=os.path.join(RUN_DIR, "detect"),
        verbose=True,
    )
    print("SELESAI TRAINING:", results)
    return 0


def export_and_install(data, run_name="leviathan_y11n"):
    from ultralytics import YOLO
    best = os.path.join(RUN_DIR, "detect", run_name, "weights", "best.pt")
    if not os.path.exists(best):
        print("!! best.pt tidak ditemukan:", best)
        return
    print("Export ONNX dari", best)
    y = YOLO(best)
    onnx_path = y.export(format="onnx", imgsz=640, opset=12, simplify=True)
    print("ONNX:", onnx_path)

    os.makedirs(MODEL_OUT, exist_ok=True)
    shutil.copy(onnx_path, os.path.join(MODEL_OUT, "model.onnx"))
    dist_models = os.path.join(BASE, "dist", "VISMOK", "models")
    if os.path.isdir(os.path.dirname(dist_models)):
        os.makedirs(dist_models, exist_ok=True)
        shutil.copy(onnx_path, os.path.join(dist_models, "model.onnx"))

    names = read_names(data)
    for d in (MODEL_OUT, dist_models):
        with open(os.path.join(d, "classes.json"), "w", encoding="utf-8") as f:
            json.dump(names, f)
    print("TERPASANG: models\\model.onnx (+ classes.json) — dev & dist")
    print("Jalankan Leviathan.exe → chip atas berubah: MODEL: ONNX")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--model", default="yolo11n.pt",
                    help="bobot dasar: yolo11n.pt / yolo11s.pt, dll.")
    ap.add_argument("--run-name", default="leviathan_y11n",
                    help="nama folder hasil di runs\\detect\\")
    ap.add_argument("--export-only", action="store_true",
                    help="skip training, cuma export best.pt → onnx")
    args = ap.parse_args()

    print("=" * 52)
    print(" LEVIATHAN TRAINING - YOLOv11n")
    print("=" * 52)
    if not check_env():
        sys.exit(1)
    if not args.export_only and not check_data(args.data):
        sys.exit(1)

    if args.export_only:
        export_and_install(args.data, args.run_name)
        return

    rc = train(args.epochs, args.imgsz, args.batch, args.data, args.model,
               args.run_name)
    if rc == 0:
        print("TRAINING SELESAI")
        export_and_install(args.data, args.run_name)
    else:
        print(f"!! training exit {rc}")


if __name__ == "__main__":
    main()
