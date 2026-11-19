# 📖 PENJELASAN KODE — Fish Feeder IoT (ESP32 + RTC + Telegram + Dashboard)

**File kode:** `Kode_Final_Vismok_Dashboard.ino`
**Proyek VISMOK — Fish Feeder IoT**
Dokumen ini menjelaskan seluruh isi kode dengan bahasa sederhana, siap dipakai untuk persiapan penilaian.

---

## 1. Gambaran Besar: Alat Ini Apa?

Sebuah **pelempar pakan ikan otomatis** yang bisa dikendalikan dari jauh lewat **Telegram**, dan sekaligus **memantau pemakaian listrik**-nya, serta terhubung ke **dashboard API** (web server) untuk monitoring & kontrol jarak jauh.

```
"Otak"    = ESP32 (mikrokontroler — komputer mini)
"Jam"     = DS3231 RTC (jam pintar pakai baterai, ingat waktu walau listrik mati)
"Kuli"    = Motor DC (melempar pakan) + Servo SG90 (membuka/menutup katup pakan)
"Mata"    = 3 sensor energi: PZEM-004T, ACS712, ZMPT101B (ukur listrik)
"Layar"   = LCD 20x4 (tampil jam + daya)
"Telepon" = Telegram Bot (suruh alat dari HP)
"Atasan"  = Dashboard API (kirim data tiap 5 detik, terima perintah balik)
```

**Alur sederhana:** tiap hari jam 07:00, 12:00, 17:00 → servo buka katup + motor putar 3 detik → pakan terlempar → laporan otomatis ke Telegram → data energi dikirim ke dashboard.

---

## 2. Tabel Perangkat Keras & Fungsinya

| Komponen | Fungsi | Pin ESP32 | Cara Kerja |
|---|---|---|---|
| ESP32 | Otak semua sistem | — | Menjalankan program, WiFi bawaan |
| RTC DS3231 | Penyimpan waktu akurat | SDA 21, SCL 22 (I2C) | Punya baterai sendiri → jam tetap jalan walau listrik/WiFi mati |
| Motor DC + L298N | Melempar pakan | ENA 25, IN1 26, IN2 27 | Driver motor dikendalikan 2 pin (arah putar) |
| Servo SG90 | Buka/tutup katup pakan | 18 (PWM) | Putar 0° = tutup, 90° = buka |
| PZEM-004T V3 | Ukur tegangan, arus, daya, energi listrik AC | Serial2 (RX 16, TX 17) | Sensor listrik paling akurat, komunikasi serial |
| ACS712 20A | Ukur arus jalur motor 12V | ADC pin 34 | Pembanding independen |
| ZMPT101B | Ukur tegangan AC | ADC pin 35 | Pembanding tegangan |
| LCD 20x4 I2C | Tampil jam & daya | SDA 21, SCL 22 (I2C 0x27) | Tampilan lokal di alat |

---

## 3. Diagram Alur Sistem

### Saat alat dinyalakan — `setup()` (jalan SEKALI, seperti "prosedur buka toko")
```
Nyalakan LCD "Booting..."
   ↓
Siapkan pin motor (mati) + servo (posisi TERTUTUP) ← penting: pakan tidak tumpah saat boot
   ↓
Cek RTC terdeteksi
   ↓
Kalibrasi ACS712 (ukur tegangan "nol" saat motor mati, 200 sampel)
   ↓
Hubungkan WiFi
   ↓
Sinkron jam RTC dari internet (NTP, zona WIB / UTC+7)
   ↓ (kalau NTP gagal + baterai RTC pernah habis → pakai waktu kompilasi sebagai cadangan)
Kirim pesan Telegram "🟢 FISH FEEDER ONLINE"
```

### Selamanya setelah itu — `loop()` (berulang tanpa henti)
```
┌────────────────────────────────────────────────────┐
│  loop()                                             │
│   ├─ Cek "sudah waktunya pakan?"   → cekJadwalPakan │
│   ├─ Update LCD                    (tiap 1 detik)   │
│   ├─ Sinkron ulang jam NTP         (tiap 24 jam)    │
│   ├─ Cek pesan Telegram masuk      (tiap 1 detik)   │
│   └─ Kirim data ke dashboard       (tiap 5 detik)   │
└────────────────────────────────────────────────────┘
```
Catatan penting: loop **tidak memakai `delay()` panjang** — semua jadwal dicek dengan `millis()` (jam internal) supaya alat tetap responsif. Ini pola pemrograman yang benar untuk IoT.

---

## 4. Penjelasan Fungsi per Fungsi

### 4.1 `cekJadwalPakan()` — mesin pakan otomatis + anti-dobel
```cpp
if (now.hour() == jadwal[i].jam && now.minute() == jadwal[i].menit) {
    if (sudahDiberiMenitIni[i] == 0) { beriPakan(...); sudahDiberiMenitIni[i] = 1; }
} else {
    sudahDiberiMenitIni[i] = 0;
}
```
**Logika:** loop berjalan ratusan kali dalam 1 menit. Tanpa flag `sudahDiberiMenitIni`, motor menyala puluhan kali dalam menit yang sama. Flag ini artinya: *"sudah pernah di menit ini?"* → hanya **1× pakan per menit jadwal**, lalu di-reset saat menit berikutnya. Ada juga `dashboardAutoFeed` — tombol matikan/nyalakan otomatis dari dashboard.

### 4.2 `beriPakan()` — inti mekanik
1. **Servo buka (0°→90°) DAN motor nyala bersamaan**
2. **Pengukuran energi dilakukan SAAT MOTOR MASIH BERPUTAR** — kode menunggu `(durasiMs - 1000)` ms dulu sebelum membaca sensor. Alasannya: kalau diukur setelah motor mati, arus terbaca ~0 A dan data tidak bermakna. Ini poin desain yang cerdas — siapkan penjelasan ini untuk dosen!
3. Motor mati + servo tutup bersamaan (durasi total dihitung akurat dengan `millis()`)
4. Catat riwayat + tambah `jumlahPakanHariIni` + kirim laporan Telegram lengkap dengan data energi

### 4.3 Tiga sensor energi — kenapa tiga?
| Sensor | Apa yang diukur | Peran |
|---|---|---|
| **PZEM-004T** | Tegangan, arus, daya, energi (kWh), frekuensi, faktor daya | Sensor "resmi" utama, paling akurat |
| **ACS712** | Arus jalur motor 12V | **Pembanding** (validasi silang) |
| **ZMPT101B** | Tegangan AC | **Pembanding** (validasi silang) |

Kalau ditanya dosen: *"ACS712 & ZMPT itu sensor pembanding untuk validasi silang dengan PZEM"* — desain yang bisa dibela secara ilmiah (redundansi pengukuran).

### 4.4 Cara hitung arus & tegangan analog (RMS)
```cpp
float selisih = voltase - acs712_zeroVoltage;
sumSquares += selisih * selisih;
...
return sqrt(sumSquares / sampel) / ACS712_SENSITIVITY;
```
- **`kalibrasiACS712()`**: tiap board punya offset tegangan tengah (idealnya 2,5 V tapi nyatanya beda-beda). Diukur saat boot (motor mati) supaya pembacaan akurat.
- **RMS** (`sqrt(mean(x²))`): arus AC itu gelombang bolak-balik — nilai instan saling meniadakan. RMS = nilai "efektif" yang setara arus DC. Ini cara hitung yang benar secara fisika.
- **ZMPT101B** juga RMS, dikalibrasi dengan faktor `zmpt_calibration` (disesuaikan dengan multimeter di lapangan).

### 4.5 `sinkronRTCdariNTP()` — jam dari internet
- Ambil waktu dari server waktu internet (`pool.ntp.org`, `time.google.com`) zona WIB (UTC+7)
- Tulis ke RTC DS3231 → **RTC menyimpan jam lokal WIB**, jadi jadwal langsung pakai jam Indonesia
- **Diulang tiap 24 jam** supaya RTC tidak meleset
- Kalau NTP gagal DAN baterai RTC pernah habis → fallback ke waktu kompilasi (`__DATE__/__TIME__`) sebagai cadangan darurat

### 4.6 Sistem perintah Telegram
```
Pesan masuk → cekPesanTelegram() → prosesPerintah()
   ├─ chat ID tidak cocok?  → TOLAK (kirim pesan "akses ditolak" + tunjukkan ID-nya)
   ├─ /feed                 → minta KONFIRMASI dulu (berlaku 60 detik)
   ├─ /yes                  → eksekusi, tapi ada COOLDOWN 30 detik antar pakan manual
   ├─ /feed 5               → pakan manual 5 detik (maks 10)
   ├─ /status /jadwal /info /help → kirim data lengkap
   └─ perintah asing        → diabaikan / diberi tahu perintah yang benar
```

**TIGA LAPIS PENGAMAN** (poin "keselamatan sistem" yang kuat untuk penilaian):
1. **Whitelist chat ID** — hanya chat terdaftar yang boleh mengendalikan
2. **Konfirmasi sebelum eksekusi** (`/feed` → `/yes`) — anti kepencet, kedaluwarsa 60 detik
3. **Cooldown 30 detik** antar pakan manual — anti overfeeding

### 4.7 Integrasi Dashboard (bagian paling "IoT")
- **Kirim:** tiap 5 detik ESP32 POST data JSON ke server:
  `voltage, current, power, energy, acs_current, zmpt_voltage, feed_count_today, time, wifi_rssi, rtc_ok, auto_feed, uptime_ms, free_heap`
- **Terima:** respons server bisa berisi perintah:
  - `FEED_NOW` → beri pakan sekarang (takaran 0,2–3,3 gram-scale → durasi = takar × 3 detik)
  - `SET_SCHEDULE` → ganti 3 slot jadwal + on/off otomatis
- **Semua perintah divalidasi ketat di sisi ESP32** — takaran di luar batas ditolak, jadwal harus tepat 3 slot, jam harus 0–23 & menit 0–59, ada cooldown. **ESP32 tidak percaya buta pada server.**
- Kalau server mati/WiFi putus: alat **tetap jalan normal** (pakan otomatis tidak bergantung internet, karena jam ada di RTC).

### 4.8 Fungsi-fungsi pendukung (bisa disebut sekilas)
| Fungsi | Tugas |
|---|---|
| `formatWaktu()` | Jam jadi `HH:MM:SS` (selalu 2 digit) |
| `infoJadwalBerikutnya()` | Hitung "pakan berikutnya 12:00 (2 jam 15 menit lagi)" |
| `perbaruiHitunganHarian()` | Reset `jumlahPakanHariIni` saat ganti hari |
| `escHTML()` / `fmtNilai()` | Keamanan format pesan HTML + penanganan sensor NaN ("❌ tidak terbaca") |
| `ikonTegangan()` / `ikonSinyal()` | Indikator emoji: 🟢 normal / 🟡 waspada / 🔴 bahaya |
| `updateLCD()` | Tampil `07:05:09 17/11` + `P:45W I:1.2A`, update tiap 1 detik |
| `tanyaKonfirmasiPakan()` / `eksekusiPakanManual()` | Alur konfirmasi dua langkah |

---

## 5. Struktur Data Kunci

```cpp
struct JadwalPakan { int jam; int menit; int durasiMotor; };

JadwalPakan jadwal[] = {
  {7,  0, 3},   // 07:00 pagi — motor 3 detik
  {12, 0, 3},   // 12:00 siang
  {17, 0, 3}    // 17:00 sore
};
```
Jadwal adalah **array** → mudah ditambah/diubah (dan memang bisa diubah dari dashboard via `SET_SCHEDULE`).

---

## 6. Q&A — Kalau Dosen Bertanya "Kenapa…?"

**T: Kenapa pakai RTC DS3231, kan bisa jam dari NTP saja?**
> WiFi bisa mati/putus. RTC punya baterai sendiri dan menyimpan waktu lokal, jadi **jadwal pakan tetap jalan walau internet down**. NTP hanya untuk *sinkronisasi* (tiap 24 jam) supaya RTC tidak meleset.

**T: Kenapa set jam dari NTP, bukan dari waktu kompilasi?**
> Waktu kompilasi hanya **cadangan darurat** kalau NTP gagal DAN baterai RTC pernah habis — akurasinya bisa meleset menit-menit. NTP diutamakan karena jauh lebih akurat, dan tidak perlu upload ulang untuk set jam.

**T: Kenapa kalibrasi ACS712 di setup()?**
> Tiap board punya *offset* tegangan tengah berbeda. Dikalibrasi saat boot (motor pasti mati) supaya pembacaan RMS akurat.

**T: Kenapa pakai RMS, bukan nilai maksimum?**
> Arus AC itu gelombang bolak-balik; nilai instan saling meniadakan. RMS = nilai efektif yang setara arus DC — cara hitung yang benar secara fisika.

**T: Kenapa pengukuran energi dilakukan saat motor masih nyala?**
> Kalau diukur setelah motor mati, arusnya ~0 A — datanya tidak bermakna. Kode sengaja menunggu `(durasi - 1 detik)` dulu sebelum membaca sensor.

**T: Kenapa durasi manual dibatasi maks 10 detik + cooldown 30 detik?**
> Melindungi ikan dari overfeeding dan melindungi mekanik dari pemakaian berlebih — desain *fail-safe*.

**T: Kenapa `setInsecure()` untuk koneksi Telegram?**
> Sertifikat TLS tidak di-embed di sketch (hemat memori & hindari gagal karena sertifikat kadaluarsa). Trade-off yang disadari; bisa diperketat dengan embed sertifikat.

**T: Kalau WiFi mati, alat masih jalan?**
> Ya — pakan otomatis bergantung pada RTC (lokal), bukan internet. Fitur Telegram & dashboard saja yang tidak tersedia sampai WiFi pulih.

**T: Kenapa servo power-nya harus dari buck/LM2596, bukan pin 5V ESP32?**
> Servo menarik arus besar saat bergerak → bisa menyebabkan ESP32 reset. Ini praktik wiring yang benar.

---

## 7. "Jurus Tunggal" — Satu Paragraf Kalau Diminta Menjelaskan Semuanya

> *"Sistem ini pelempar pakan ikan otomatis berbasis ESP32. Jadwal disimpan di RTC DS3231 yang disinkron dari internet (NTP, zona WIB) sehingga tetap akurat walau tanpa internet. Saat waktu jadwal tiba, servo membuka katup dan motor DC melempar pakan selama 3 detik, dengan flag anti-dobel agar tidak terpicu berulang dalam menit yang sama. Pemakaian energinya dipantau tiga sensor — PZEM-004T sebagai utama, ACS712 dan ZMPT101B sebagai pembanding RMS — dan hasilnya ditampilkan di LCD, dilaporkan ke Telegram Bot, serta dikirim tiap 5 detik ke dashboard API yang juga bisa mengirim perintah pakan atau ubah jadwal yang divalidasi ketat di sisi ESP32. Semua kontrol manual lewat Telegram memerlukan whitelist chat ID, konfirmasi dua langkah, dan cooldown sebagai lapisan keselamatan."*

---

## 8. Glosarium Istilah Teknis (kalau ditanya artinya)

| Istilah | Artinya |
|---|---|
| NTP | Network Time Protocol — cara komputer ambil jam akurat dari internet |
| RMS | Root Mean Square — nilai efektif sinyal AC (cara baku mengukur arus/tegangan AC) |
| I2C | Protokol komunikasi 2 kabel (SDA/SCL) untuk RTC, LCD, dsb. |
| PWM | Pulse Width Modulation — cara servo dikendalikan lewat lebar pulsa |
| JSON | Format data teks terstruktur untuk komunikasi dengan server |
| API/HTTP POST | Cara ESP32 mengirim data ke web server |
| millis() | Jam internal ESP32 (ms sejak nyala) — pengganti delay() agar sistem responsif |
| Whitelist | Daftar yang diizinkan (di sini: chat ID yang boleh mengendalikan alat) |
| Fallback | Cadangan saat cara utama gagal (contoh: waktu kompilasi saat NTP gagal) |
| Flag | Variabel penanda 1/0 (contoh: `sudahDiberiMenitIni` anti-dobel pakan) |
