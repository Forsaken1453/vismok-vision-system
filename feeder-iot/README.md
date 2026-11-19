# Dashboard Pelempar Pakan Ikan Otomatis

Monitoring & kontrol pelempar pakan ikan berbasis ESP32, dengan dashboard web lokal.
**Tanpa hosting. Tanpa biaya bulanan. Data tidak keluar dari rumah kamu.**

```
ESP32 (rumah/kolam)  ──WiFi──▶  Laptop kamu (server Flask)  ──WiFi──▶  Browser HP
```

---

## Fitur

| Fitur | Keterangan |
|---|---|
| Monitoring real-time | Tegangan AC, daya, arus AC, energi kWh, arus motor, sinyal WiFi |
| Estimasi biaya energi | Konsumsi harian/bulanan dan proyeksi biaya dengan tarif PLN yang bisa diatur |
| Grafik langsung | 1 / 5 / 12 menit, Chart.js tersimpan lokal (offline) |
| Kontrol jadwal | 3 slot (default 07:00, 12:00, 17:00), takaran per slot |
| Takaran fleksibel | 1 takar = 3 detik putar motor. Atur 0.2 – 5.0 takar per slot |
| Feed manual | Tombol "Feed Sekarang" dari dashboard |
| Deteksi gagal | Motor macet, daya AC hilang, jadwal terlewat, sensor putus, RAM habis |
| Notifikasi | Banner peringatan + toast + bunyi beep di browser |
| RTC | DS3231 sebagai jam utama, sinkron NTP saat ada internet |

### Deteksi "Pelempar Gagal"

| Kode | Arti | Cara deteksi |
|---|---|---|
| `MOTOR_NO_CURRENT` | Motor tidak berputar | Peak arus ACS712 < 0.15 A saat motor running |
| `NO_AC_POWER` | Daya AC hilang | PZEM004T tegangan < 20 V |
| `SCHEDULE_MISSED` | Jadwal terlewat | Lewat jadwal + 30 detik tanpa trigger |
| `ZMPT_DROPOUT` | Sensor ZMPT putus | ZMPT baca < 5 V sementara PZEM > 20 V |
| `OFFLINE` | ESP32 tidak kirim data | Tidak ada data masuk > 10 detik |
| `RTC_NOT_READY` | RTC belum siap | DS3231 tidak terbaca |
| `WIFI_WEAK` | Sinyal lemih | RSSI < -75 dBm |
| `LOW_MEMORY` | RAM ESP32 habis | Free heap < 30 KB |

---

## Persyaratan

- [x] Laptop Windows dengan WiFi
- [x] Python 3.10+ (sudah terinstall)
- [ ] ESP32 DevKit V4 (38-pin)
- [ ] Sensor: ZMPT101B, ACS712, PZEM004T-V4
- [ ] Modul RTC DS3231
- [ ] Motor RS555 12V + driver (BTS7960 / L298N / MOSFET)
- [ ] Adaptor 12V 2A
- [ ] Kabel USB untuk upload firmware

> **Peringatan listrik:** proyek ini menyentuh tegangan AC 220V. Baca bagian
> peringatan di `docs/WIRING.md` sebelum merakit.

---

## Cara Pakai

### Langkah 1 — Jalankan dashboard di laptop

Klik 2x **`run.bat`**

Browser otomatis terbuka. Lihat URL yang ditampilkan di jendela hitam:

```
  Di laptop     : http://127.0.0.1:8080
  Di HP (WiFi)  : http://192.168.1.3:8080
```

Biarkan jendela hitam tetap terbuka. Kalau ditutup, server mati.

### Langkah 2 — Upload firmware ke ESP32

> **Pakai kode capstone Telegram + LCD 20x4 yang dikirim untuk diperbaiki?**
> Buka **`firmware/Kode_Final_Vismok_Dashboard.ino`**. File ini mempertahankan
> firmware capstone dan menambahkan telemetry serta penerimaan perintah feed
> dan jadwal dari dashboard. Perintah dashboard hanya tersedia setelah sketch
> ini di-upload; firmware lama hanya mengirim monitoring.

1. Edit `firmware/config.h` (untuk `fish_feeder.ino`)
   atau konfigurasi di bagian atas sketch capstone:
   - `WIFI_SSID` dan `WIFI_PASSWORD` → isi WiFi rumah kamu
   - `DASHBOARD_URL` → `http://<IP-LAPTOP>:8080/api/ingest`
     (contoh `http://192.168.2.106:8080/api/ingest`)
   - `BOT_TOKEN` dan `CHAT_ID` → isi kredensial Telegram milikmu
   - Pada sketch capstone: `ACS712_SENSITIVITY` dan `zmpt_calibration`
     sesuai hasil kalibrasi sensor
2. Buka Arduino IDE → buka sketch yang dipakai:
   `fish_feeder.ino`, `fish_feeder_dashboard.ino`, atau
   `Kode_Final_Vismok_Dashboard.ino` untuk kode capstone di atas
3. Install library via Library Manager:
   - `ArduinoJson` (arduinojson.org)
   - `RTClib` (Adafruit)
   - `Adafruit BusIO`
   - `LiquidCrystal_I2C`, `PZEM004Tv30`, `ESP32Servo`, `UniversalTelegramBot`
4. Pilih board **ESP32 Dev Module**, port USB yang sesuai
5. Upload

### Langkah 3 — Pasang library di laptop (sudah otomatis oleh run.bat)

`run.bat` otomatis memasang Flask kalau belum ada.

Kalau mau manual:
```
pip install -r app/requirements.txt
```

### Langkah 4 — Buka dari HP

HP dan laptop harus di WiFi yang sama, lalu buka `http://192.168.1.3:8080`
di browser HP. Tambah ke home screen supayaeasy diakses.

---

## Struktur Project

```
fish-feeder-dashboard/
├── run.bat                    <- klik ini untuk mulai
├── firmware/
│   ├── fish_feeder.ino        <- kode ESP32
│   └── config.h               <- pin map + SSID/password + jadwal
├── app/
│   ├── server.py              <- server Flask
│   ├── requirements.txt
│   ├── core/
│   │   ├── storage.py         <- state + ring buffer + settings
│   │   ├── billing.py         <- akumulasi energi + estimasi biaya
│   │   └── alerts.py          <- aturan deteksi gagal
│   ├── web/
│   │   ├── index.html
│   │   ├── app.js
│   │   ├── style.css
│   │   └── vendor/chart.min.js   <- Chart.js lokal, offline
│   └── data/
│       ├── settings.json      <- setelan dashboard, termasuk tarif
│       └── billing.json       <- ringkasan konsumsi persisten
└── docs/
    └── WIRING.md              <- peta pin + troubleshooting
```

---

## API

| Method | Endpoint | Dipanggil oleh | Fungsi |
|---|---|---|---|
| `POST` | `/api/ingest` | Firmware dashboard/capstone (tiap 1–5 detik) | Terima telemetry terstruktur atau format datar capstone; kirim perintah balik |
| `POST` | `/api/telemetry` | Firmware lama (monitoring saja) | Terima telemetry datar tanpa kanal perintah |
| `GET` | `/api/state` | Browser (tiap 1 detik) | Status lengkap + alert |
| `GET` | `/api/history` | Browser (tiap 2 detik) | Data grafik |
| `GET` | `/api/export.xlsx` | Browser | Simpan salinan di `D:\CAPSTONE` dan unduh workbook Excel `.xlsx` |
| `POST` | `/api/settings` | Browser | Simpan tarif listrik (Rp/kWh) |
| `POST` | `/api/history/clear` | Browser | Hapus history |
| `POST` | `/api/feed_now` | Browser | Feed manual |
| `POST` | `/api/schedule` | Browser | Simpan jadwal |
| `GET` | `/api/meta` | Browser | Info metrik |

**Cara kerja perintah:** browser kirim perintah ke Flask → disimpan di antrean →
ESP32 mengambilnya di balasan `/api/ingest` berikutnya (maks 1 detik kemudian).
Kanal perintah dashboard hanya bekerja jika firmware mengirim marker
`dashboard_control` dan membaca `commands` dari balasan `/api/ingest`.

---

## Pengaturan Firewall (Windows)

Supaya HP bisa mengakses server, buka port 8080. Jalankan PowerShell **sebagai Administrator**:

```powershell
New-NetFirewallRule -DisplayName "Fish Feeder Dashboard" `
  -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```

Kalau masih tidak bisa diakses dari HP:
1. Pastikan HP & laptop di WiFi yang sama (bukan WiFi Tamu/Public)
2. Cek MATLAB firewall laptop
3. Coba dari HP: `http://<IP-LAPTOP>:8080`

---

## Storage

| Komponen | Ukuran |
|---|---|
| Python 3.12 | 149 MB |
| Flask + dependensi | 15 MB |
| Chart.js lokal | 0.2 MB |
| Kode project | < 1 MB |
| **Total** | **~165 MB** |

History grafik disimpan di RAM saja — **hilang saat aplikasi ditutup**.
Ini disengaja supaya tidak ada file log yang menumpuk.
Kalau butuh riwayat berhari-hari, sambungkan Thingspeak / InfluxDB / Google Sheets.
Ringkasan energi harian/bulanan dan pembacaan meter terakhir disimpan lokal di
`app/data/billing.json`. Perkiraan biaya hanya berlaku untuk beban yang melewati
PZEM, memakai tarif yang dimasukkan pengguna (nilai awal Rp1.444,70/kWh perlu
disesuaikan dengan golongan pelanggan), serta tidak mencakup pajak/biaya
administrasi PLN. Titik baca energi pertama menjadi baseline dan tidak dihitung
sebagai pemakaian; proyeksi bulanan baru muncul setelah minimal satu hari data.

---

## Troubleshooting

| Masalah | Solusi |
|---|---|
| "Python tidak ditemukan" | Install dari python.org, centang **Add Python to PATH** |
| Browser tidak terbuka otomatis | Buka manual `http://127.0.0.1:8080` |
| Dashboard "ESP32 offline" | Cek `SERVER_HOST` di `config.h` = IP laptop. Cek WiFi ESP32. |
| IP laptop berubah | DHCP. Cek `ipconfig`, update `config.h`, upload ulang firmware |
| Port 8080 sudah dipakai | Ubah `PORT` di `server.py` dan `SERVER_PORT` di `config.h` |
| HP tidak bisa akses | Cek firewall (di atas), pastikan WiFi sama |
| Nilai sensor tidak masuk akal | Lihat `docs/WIRING.md` bagian troubleshooting |

---

## customizing

**Ganti jadwal default** → edit `DEFAULT_SLOT_*` di `firmware/config.h`
(tapi lebih mudah ubah dari dashboard, nanti tersimpan di ESP32).

**Ganti durasi per takaran** → edit `MOTOR_BASE_SECOND` di `config.h`
(default 3.0 detik = 1 takar).

**Ganti ambang deteksi motor macet** → edit `MOTOR_MIN_PEAK_CURRENT` di `config.h`
(default 0.15 A).

**Ubah Frekuensi push data** → edit `TELEMETRY_INTERVAL_MS` di `config.h`
(default 1000 ms = 1 detik).

---

*Sensor: ZMPT101B · ACS712 · PZEM004T-V4 · RTC DS3231 · Motor RS555 12V*
*Dashboard lokal — tidak ada data yang dikirim ke internet*