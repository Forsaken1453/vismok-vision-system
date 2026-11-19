# 📷 PANDUAN DATASET LEVIATHAN
### Target: 8 jenis — Guppy, Koi, Cupang, Molly, Komet, Chana, Arwana, Ikan Mas

---

## 1. Target jumlah foto per jenis

| Jenis | Minimum (level demo pameran) | Idealan |
|---|---|---|
| komet | **200** | 300+ |
| ikan mas | **200** | 300+ |
| koi | **200** | 300+ |
| guppy | 150 | 250+ |
| molly | 100 | 200+ |
| cupang | 100 | 200+ |
| chana | 80 | 150+ |
| arwana | 80 | 150+ |

> **Catatan penting:** pasangan *komet vs ikan mas vs koi* adalah yang paling sulit
> dibedakan (bentuk dan warnanya mirip). Usahakan jumlahnya lebih banyak, dan jangan
> ambil semua fotonya dari satu sumber video yang sama — model bisa terkecoh
> mempelajari "warna/kualitas video itu" alih-alih bentuk asli ikan.

## 2. Sumber foto (campur semuanya!)

| Sumber | Cara | Catatan |
|---|---|---|
| **Foto sendiri** ⭐ (tersuci) | Foto ikan di kantong plastik, di bak, di ember, air keruh & bening | Kondisi asli penggunaan! Kamera HP cukup (12MP+) |
| **YouTube** | Cari "guppy fish 4k", "arwana", "ikan koi" → pakai `tools/frames_from_video.py` | Ambil frame dari video resolusi tinggi |
| **Roboflow Universe** | Daftar gratis → cari "aquarium fish", "goldfish", "koi" | Download dataset yang relevan |
| **Google Images** | Simpan gambar yang bagus (tanpa watermark) | Untuk menambah variasi |

**Rasio campur yang sehat:** ±40% foto sendiri + ±40% YouTube/internet + ±20% dataset publik.

## 3. Ekstrak frame dari video

```powershell
cd D:\Leviathan
python tools\frames_from_video.py "C:\path\ke\video.mp4" datasets\guppy\video1 --every 1.5
```

- `--every 1.5` = ambil 1 frame tiap 1.5 detik (video gerakan cepat → 0.5; lambat → 2.0).
- Bisa diulang untuk beberapa video, semuanya masuk folder output yang sama.
- Setelah selesai, hapus manual frame yang blur / duplikat.

## 4. Struktur folder dataset (penting!)

```
datasets/
  guppy/       ← semua foto TANPA subfolder (flat) satu folder per jenis
  molly/
  cupang/
  komet/
  ikan_mas/    ← nama klas harus tanpa spasi, underscore! (bukan "mas" / "Ikan Mas")
  koi/
  chana/
  arwana/
```

**PENTING:** nama folder = nama class YOLO = isi kolom `class_name` di tabel `species`
database Leviathan. Default kami sudah: `guppy, koi, cupang, molly, komet, chana,
arwana, ikan_mas`. Justru karena itu **gunakan nama folder `ikan_mas`** (pakai
underscore, tanpa spasi). Konsisten satu nama, jangan ganti-ganti!

## 5. Labeling di Roboflow (gratis)

1. Daftar akun gratis di roboflow.com
2. **New Project** → tipe *Object Detection*
3. **Upload** semua foto (drag & drop per folder jenis)
4. Buat class: `guppy, koi, cupang, molly, komet, chana, arwana, ikan_mas`
5. **Annotate**: gambar box mengikuti badan ikan secara ketat (bukan kotak kecil di
   bagian tengah saja). Kalau ada 3 ikan dalam satu foto → buat 3 box.
6. **Generate** → preprocessing none, augmentasi ringan saja
7. **Export format: YOLOv8/YOLOv11 (Object Detection)** → **Download zip**

## 6. Cek kualitas sebelum training

- [ ] Tidak ada foto buram / ikan hanya 10-pixel di pojok
- [ ] Semua jenis ikan sudah ter-annotate di semua foto
- [ ] Ada foto ikan dalam kantong plastik dan di air keruh (kondisi toko nyata!)
- [ ] Split train/val/test 80/15/5 (Roboflow otomatis)
- [ ] Buang foto aneh: ikan duplikat, frame hitam, atau ikan terbawa aneh

---

Selanjutnya → **`TRAINING_QUICKSTART.md`**: latih YOLOv11 pakai RTX 3050-mu, lalu
export ke `models/model.onnx` supaya Leviathan otomatis memakainya.
