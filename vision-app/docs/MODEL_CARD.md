# Model Card — VISMOK Fish Detector (YOLOv11s)

## Ringkasan

| Item | Detail |
|---|---|
| Nama model | VISMOK Fish Detector |
| Tugas | Object detection (8 kelas ikan air tawar/hias) |
| Arsitektur | YOLOv11s (Ultralytics), fine-tuned |
| Format deploy | ONNX (opset 12), output `[1, 12, 8400]` |
| Runtime | ONNX Runtime, CPU |
| Input | RGB 768×768, normalisasi 0–1 |
| Ukuran | ±36 MB |
| Versi | Round-3 fine-tune (interupsi epoch 91 → fine-tune 120 epoch) |

## Kelas

| ID | Kelas | Nama umum |
|---|---|---|
| 0 | guppy | Guppy |
| 1 | koi | Koi |
| 2 | cupang | Cupang / Betta |
| 3 | molly | Molly |
| 4 | komet | Komet / Comet goldfish |
| 5 | chana | Channa / Snakehead |
| 6 | arwana | Arwana |
| 7 | ikan_mas | Ikan mas / Common carp |

Urutan kelas disimpan di `classes.json` dan **harus sama** dengan urutan training.

## Data

| Tahap | Detail |
|---|---|
| Sumber foto | Wikimedia Commons (lisensi bebas) |
| Total terkumpul | 2.569 foto |
| Auto-label | YOLO-World (`yolov8s-worldv2.pt`), conf ≥ 0,30; kotak < 4% luas dibuang |
| Foto berlabel | 1.365 (53%) — sisanya dibuang karena tidak ada ikan valid |
| Split | 1.229 train / 136 valid (90/10) |
| Distribusi kelas (kotak) | koi 320 · ikan_mas 310 · cupang 236 · arwana 222 · molly 218 · chana 184 · guppy 173 · komet 171 |

## Pelatihan

| Parameter | Nilai |
|---|---|
| Base model | `yolo11s.pt` |
| Image size | 768 |
| Batch | 12 |
| Epochs | 120 (fine-tune dari checkpoint round-3) |
| GPU | NVIDIA RTX 3050 6 GB |
| Framework | PyTorch 2.5.1 + CUDA 12.1, Ultralytics |

## Metrik (136 foto validasi terpisah)

| Metrik | Nilai |
|---|---|
| mAP@50 | **0,977** |
| mAP@50-95 | 0,951 |
| Presisi | 0,926 |
| Recall | 0,926 |

| Kelas | mAP@50 | Recall |
|---|---|---|
| chana | 0,995 | 1,000 |
| komet | 0,995 | 1,000 |
| guppy | 0,995 | 1,000 |
| cupang | 0,995 | 0,932 |
| molly | 0,984 | 0,919 |
| arwana | 0,962 | 0,900 |
| koi | 0,951 | 0,750 |
| ikan_mas | 0,942 | 0,905 |

**Uji negatif:** foto wajah manusia tidak menghasilkan deteksi (false positive = 0 pada uji ini).

## Keterbatasan

1. **Koi vs ikan mas** — keduanya karper (*Cyprinus*); pembeda terutama pola warna. Recall koi 0,750 adalah titik terlemah.
2. **Kelas tertutup** — model hanya mengenali 8 kelas; ikan spesies lain tidak dikenali (skor rendah / tidak terdeteksi).
3. **Kondisi gambar** — akurasi turun pada gambar blur, cahaya minim, atau ikan sangat kecil di frame.
4. **Domain data** — sebagian besar foto berasal dari internet (akuarium/kolam), bukan kondisi toko; foto lapangan nyata dapat berbeda.
5. **Bukan diagnosa kesehatan** — model tidak mendeteksi penyakit ikan.

## Penggunaan yang Disarankan

- ✅ Identifikasi jenis ikan untuk rekomendasi pakan di toko/UMKM.
- ✅ Mode MANUAL (foto tunggal) untuk hasil paling akurat.
- ⚠️ Mode AUTO cocok untuk demo; konfirmasi 2 frame menekan kedipan.
- ❌ Bukan alat diagnosis penyakit, bukan penentu harga otomatis.

## Reproduksi

```bash
cd vision-app
python tools/collect_dataset.py                  # kumpulkan foto
python tools/autolabel_dataset.py --conf 0.30    # auto-label + split
python tools/train_leviathan.py --model yolo11s.pt --epochs 120 --imgsz 768 --batch 12
# export ONNX + pasang otomatis ke models/ dan dist/
python tools/train_leviathan.py --export-only
```

## Rujukan

- Ultralytics YOLO11: https://docs.ultralytics.com/models/yolo11/
- YOLO-World: https://docs.ultralytics.com/models/yolo-world/
- ONNX Runtime: https://onnxruntime.ai/
