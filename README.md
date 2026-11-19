# 🐟 VISMOK × Fish Feeder IoT — Capstone Kelompok 4, Rombel 11

Ekosistem budidaya & penjualan ikan berbasis IoT + Computer Vision untuk UMKM
**Toko Ikan Aseli Ngawi**.

Sistem ini menyatukan dua subsistem yang saling melengkapi:

```
                     ┌─────────────────────────────┐
   Kamera ──────────►│  SISTEM VISI (VISMOK)       │
                     │  YOLOv11s · ONNX · CPU      │
                     │  → jenis ikan + lokasi      │
                     └──────────────┬──────────────┘
                                    │ rekomendasi pakan
                                    ▼
                     ┌─────────────────────────────┐
   Sensor ──────────►│  PELEMPAR PAKAN IoT         │
   PZEM/ACS/ZMPT     │  ESP32 · RTC · Servo · Motor│
   ◄──── Telegram ───┤  jadwal 07:00/12:00/17:00   │
   ◄──── Dashboard ──┤  kontrol + monitoring energi│
                     └─────────────────────────────┘
```

## ✨ Fitur Utama

### Subsistem 1 — Sistem Visi (aplikasi desktop `VISMOK`)
- **Deteksi 8 jenis ikan real-time**: guppy, koi, cupang, molly, komet, chana, arwana, ikan mas
- **YOLOv11s** di-*fine-tune* khusus, diekspor ke **ONNX** → jalan di CPU tanpa PyTorch
- **mAP@50 = 0,977**, mAP@50-95 = 0,951, recall 0,926 (136 foto uji terpisah)
- Dataset dibangun otomatis: **2.569 foto** dikumpulkan + **auto-label YOLO-World** (tanpa anotasi manual) → 1.365 foto berlabel
- Rekomendasi pakan + tips perawatan per jenis ikan (SQLite)
- GUI futuristik (PySide6/Qt), mode kamera webcam & HP (**DroidCam** via "IP HP...")
- Kwitansi PDF (QPdfWriter), riwayat deteksi, panel admin (PIN)
- **100% offline** saat pameran/toko

### Subsistem 2 — Pelempar Pakan IoT (`feeder-iot`)
- **Jadwal otomatis** 07:00 / 12:00 / 17:00 — jam dari **DS3231 RTC** disinkron **NTP (WIB)**, tetap akurat walau internet mati
- **Kontrol jarak jauh via Telegram Bot**: `/menu`, `/feed`, `/status`, `/jadwal`, `/info`, `/help`
- **Keamanan berlapis**: whitelist chat ID, konfirmasi 2 langkah, cooldown 30 detik
- **Kontrol via web dashboard** — perintah divalidasi ketat di sisi ESP32
- **Monitoring energi 3 sensor**: PZEM-004T V3 (utama: V/I/P/kWh/Hz/PF), ACS712 20A (arus jalur motor), ZMPT101B (tegangan) → validasi silang
- **Anti-dobel pakan** (flag per menit), durasi motor dapat diatur dari dashboard
- LCD 20×4 menampilkan jam & daya

## 🧠 Keputusan Teknis (berbasis pengujian)

| Metode diuji | Hasil | Keputusan |
|---|---|---|
| YOLO-World open-vocabulary sebagai verifikasi jenis | 4/48 cocok | ❌ ditolak |
| CLIP zero-shot klasifikasi | 62%, probabilitas mendatar ~0,13 | ❌ ditolak |
| **Fine-tuning YOLOv11s** | **mAP50 0,977** | ✅ dipakai |

Logika feeder: **time-triggered open-loop + rule-based interlocks** (bukan fuzzy) —
dipilih karena jadwal pakan baku, andal, dan mudah diaudit. Kecerdasan sistem
berada di lapisan visi (deep learning) dan integrasi data.

## 📁 Struktur Repo

```
vision-app/        Aplikasi desktop VISMOK (PySide6 + ONNX Runtime)
  app/             kode aplikasi (core detector, DB, UI)
  models/          model.onnx (YOLOv11s) + classes.json
  tools/           collect_dataset, autolabel_dataset, train_leviathan, make_icon
  tests/           evaluasi model & uji kamera
  docs/            panduan dataset & training

feeder-iot/        Firmware ESP32 + dashboard web
  firmware/        sketch Arduino (.ino) + dokumen penjelasan kode
  app/             server dashboard (Python)
  docs/            wiring, panduan
  poster/          poster capstone
```

## 🚀 Menjalankan

### Aplikasi visi
```bash
cd vision-app
pip install -r requirements.txt
python run.py
```
Atau build exe: `build_exe.cmd` (PyInstaller onedir) → `dist/VISMOK/VISMOK.exe`.

### Dashboard + firmware
1. `cd feeder-iot`, jalankan `run.bat` (server dashboard Python).
2. Buka `firmware/Kode_Final_Vismok_Dashboard/Kode_Final_Vismok_Dashboard.ino`
   di Arduino IDE (board *ESP32 Dev Module*), isi kredensial WiFi/Bot di bagian atas,
   sesuaikan `DASHBOARD_URL` dengan IP server, lalu upload.
3. Kalibrasi `ACS712_SENSITIVITY` & `zmpt_calibration` dengan multimeter.

## 🔐 Kredensial

Semua kredensial di repo ini **placeholder** — isi dengan milikmu sendiri:

| Placeholder | Keterangan |
|---|---|
| `ISI_SSID_WIFI` / `ISI_PASSWORD_WIFI` | WiFi 2.4 GHz (ESP32 tidak mendukung 5 GHz) |
| `ISI_BOT_TOKEN_DARI_BOTFATHER` | Token bot dari @BotFather |
| `ISI_CHAT_ID_GRUP` | ID chat/grup yang diizinkan mengendalikan alat |

## 📊 Ringkasan Hasil

| Metrik | Nilai |
|---|---|
| mAP@50 (136 foto uji) | **0,977** |
| mAP@50-95 | 0,951 |
| Recall | 0,926 |
| Kelas terendah | 0,942 (ikan mas) |
| Uji negatif wajah manusia | Lolos (tidak terdeteksi) |
| Inferensi | ONNX Runtime CPU, tiap 3 frame, ±300 ms |
| Telemetri dashboard | tiap 5 detik |
| Sensor energi | PZEM-004T V3 + ACS712 20A + ZMPT101B |

## 📄 Lisensi

MIT — bebas digunakan dengan atribusi.
