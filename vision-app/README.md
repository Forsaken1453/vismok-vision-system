# ◈ LEVIATHAN
### Asisten Vision Pakan Ikan — kamera lihat ikan, keluar rekomendasi pakan yang cocok.

Aplikasi desktop (Windows) untuk toko / pembudidaya ikan: taruh ikan di depan
kamera (webcam atau HP via DroidCam), sistem mendeteksi jenisnya dengan model
YOLO, lalu menampilkan **rekomendasi produk pakan yang dijual di tokomu** +
tips perawatan ikan.

---

## Fitur MVP (v1)

| Fitur | Status |
|---|---|
| Deteksi 8 jenis ikan: guppy, koi, cupang, molly, komet, chana, arwana, ikan mas | taruh `models/model.onnx` |
| Mode demo tanpa model (deteksi acak, untuk uji UI / cadangan pameran) | siap |
| Kamera: webcam laptop / webcam USB / DroidCam HP (URL MJPEG) | siap |
| Rekomendasi pakan berprioritas 1-3 + frekuensi & dosis pemberian | siap |
| Detail ikan: habitat, sifat, suhu, pH, ukuran dewasa, tips perawatan | siap |
| PILIH MANUAL (grid 8 jenis) kalau kamera gagal atau deteksi salah | siap |
| Panel Admin (PIN default 2026): katalog produk, prioritas rekomendasi, pengaturan kamera & threshold | siap |
| Snapshot tiap deteksi tersimpan di `data/snapshots/` | siap |
| UI futuristik deep-sea, fullscreen kiosk | siap |

## Menjalankan

```powershell
cd D:\Leviathan
python run.py
```

Pertama kali dijalankan: database SQLite + seed data dibuat otomatis.
Tanpa file `models/model.onnx`, aplikasi jalan dalam **MODE DEMO**
(chip status menampilkan `MODEL: DEMO`, deteksi simulasi tiap beberapa detik).

## Struktur project

```
Leviathan/
  run.py                    entry point aplikasi
  requirements.txt          dependensi runtime
  app/
    config.py               path & konstanta
    core/
      database.py           schema SQLite + seed data ikan & pakan
      camera.py             sumber kamera (webcam / DroidCam)
      detector.py           YoloOnnxDetector (ONNX) + DummyDetector (demo)
    ui/
      theme.py              tema QSS deep-sea futuristic
      widgets.py            CameraView (scanline + box deteksi), kartu, chip
      pages.py              Standby, Hasil, Detail, Manual, Admin
      main_window.py        navigasi halaman + loop kamera/deteksi
  models/                   taruh model.onnx hasil training di sini
  docs/
    DATASET_GUIDE.md        panduan kumpul & label dataset
    TRAINING_QUICKSTART.md  training di RTX 3050 + export ONNX
  tools/
    frames_from_video.py    ekstrak frame video jadi dataset foto
  data/
    leviathan.db            database (dibuat otomatis)
    snapshots/              hasil snapshot deteksi
```

## Panel Admin (tombol gear di layar kamera, PIN 2026)

- **KATALOG PAKAN** — kelola produk yang dijual: nama, merek, bentuk,
  ukuran pellet, protein, harga, stok. (Data starter berupa dummy; timpa
  dengan produk asli tokomu.)
- **REKOMENDASI** — atur produk yang direkomendasikan per jenis ikan,
  urutan prioritas 1 sampai 3.
- **SISTEM** — pilih kamera (webcam index / URL DroidCam), batas kepercayaan
  deteksi, ganti PIN, ubah nama toko.

## Model YOLO

1. Baca `docs/DATASET_GUIDE.md` → kumpulin & label dataset
2. Baca `docs/TRAINING_QUICKSTART.md` → latih di RTX 3050
3. Salin hasil export ke `models/model.onnx`
4. Jalankan ulang aplikasi → otomatis mode ONNX

## Build .exe (setelah model siap)

```powershell
pip install pyinstaller
pyinstaller --noconsole --onedir --name Leviathan run.py
```

Hasil: `dist\Leviathan\Leviathan.exe` (mode one-folder, startup cepat).
Pastikan folder `models/` dan `data/` ikut disalin di samping exe itu
(atau jalanin `Leviathan.exe` dari folder project saat demo).
