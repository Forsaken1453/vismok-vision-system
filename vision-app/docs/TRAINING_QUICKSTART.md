# QUICKSTART TRAINING YOLOv11 (RTX 3050 6GB — Lenovo LOQ i5-12450H)

Panduan singkat dari dataset sampai model ONNX siap dipakai Leviathan.
Estimasi total waktu: satu sore (termasuk download & training).

---

## 0. Prasyarat

```powershell
pip install ultralytics onnx onnxslim
```

- Dataset hasil labeling Roboflow (format YOLOv8/v11), sudah di-unzip.
- GPU RTX 3050 harus terdeteksi PyTorch. Cek:

```python
import torch
print(torch.cuda.is_available())   # harus True
```

Kalau hasilnya False, install ulang torch versi CUDA:

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

## 1. Arahkan data.yaml

Saat Roboflow dataset di-unzip, cari file `data.yaml`. Pastikan isinya
pakai path absolut, contoh:

```yaml
path: D:/Leviathan/train       # folder hasil unzip
train: train/images
val: valid/images
nc: 8
names: [guppy, koi, cupang, molly, komet, chana, arwana, ikan_mas]
```

PENTING: daftar `names` harus sama persis (penulisan & urutan) dengan kolom
`class_name` di database Leviathan. Urutan bebas, nama harus sama.

## 2. Training

```python
from ultralytics import YOLO

model = YOLO("yolo11n.pt")            # nano: cepat & ringan, cocok untuk demo
model.train(
    data="D:/Leviathan/train/data.yaml",
    epochs=80,                        # 60-100 cukup untuk 8 kelas
    imgsz=640,
    batch=16,                         # kalau GPU memory kurang, turunkan ke 8
    device=0,                         # pakai RTX 3050
    workers=4,
    patience=25,                      # early stopping
    name="leviathan_v1",              # nama folder hasil training
)
```

Hasil terbaik akan tersimpan di:
`runs/detect/leviathan_v1/weights/best.pt`

## 3. Evaluasi

Buka dua file di folder hasil training:

- `confusion_matrix.png` - kalau komet vs ikan mas vs koi saling tertukar,
  tambah foto untuk kelas-kelas itu lalu train ulang.
- `results.png` - cek kurva mAP50 & loss apakah masih naik atau sudah stabil.

## 4. Export ke ONNX

```python
from ultralytics import YOLO
m = YOLO("runs/detect/leviathan_v1/weights/best.pt")
m.export(format="onnx", imgsz=640, simplify=True)
```

Hasilnya file `best.onnx`. Salin ke folder Leviathan dengan nama persis:

```
D:\Leviathan\models\model.onnx
```

Setelah file itu ada, Leviathan otomatis masuk mode ONNX (chip status di layar
utama berubah dari MODEL: DEMO menjadi MODEL: ONNX). Nama class diambil dari
metadata ONNX milik ultralytics - tidak perlu diatur ulang.

## 5. Tes model di luar GUI

```python
import cv2
from app.core.detector import load_detector
det = load_detector(["guppy","koi","cupang","molly","komet","chana","arwana","ikan_mas"])
img = cv2.imread("test_guppy.jpg")
print(det.detect(img))
```

## 6. Tips khusus pameran

- Threshold deteksi diatur di Panel Admin (default 0.55). Kalau demo sering
  gagal kenal, turunkan ke 0.45 agar lebih sensitif; kalau sering salah kenal,
  naikkan ke 0.50.
- Untuk kondisi pameran yang tidak terkontrol, sediakan foto/objek cadangan,
  atau mode PILIH MANUAL di halaman kamera.
- Bawa rencana cadangan: rekam videoikan demo di HP, pantau jangan sampai
  kamera/laptopi crash di booth.

---

Setelah model.onnx tersedia, cukup jalankan `python run.py` di folder
D:\Leviathan. Leviathan otomatis memakai model asli tanpa perubahan kode.
