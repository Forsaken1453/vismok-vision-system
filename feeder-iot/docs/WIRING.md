# Wiring — Pelempar Pakan Ikan Otomatis

> ⚠️ **PERINGATAN KEAMANAN**
> Proyek ini menyentuh **tegangan AC mains 220V** (ZMPT101B, PZEM004T, adaptor 12V).
> - **Jangan** menyentuh board saat terpasang listrik.
> - Gunakan **enclosure** atau box plastik, bukan paparan PCB telanjang.
> - Pasang **sekring (fuse)** pada jalur AC.
> - Pastikan transformator step-down untuk motor terisolasi dari sisi sekunder.
> - PZEM004T-V4 sudah terisolasi optocoupler, tapi modul ZMPT101B **tidak**.
>   Rakit di luar ruangan dengan hati-hati. Pastikan Anda paham batasnya.

---

## 1. Ringkasan Komponen

| Komponen | Fungsi | Catatan |
|---|---|---|
| ESP32 DevKit V4 (38-pin) | Otak sistem | Dual core, WiFi built-in |
| ZMPT101B | Sensor tegangan AC | **Tidak isolated** |
| ACS712 | Sensor arus DC motor | Pilih 5A / 30A / 100A |
| PZEM004T-V4 | Meter AC (V/A/W/Wh/Hz/PF) | UART, sudah isolated |
| DS3231 | RTC untuk jadwal | 더 akurat dari DS1307 |
| Motor RS555 12V | Pelempar pakan | Motor getar_continuous rotation |
| Driver MOSFET / BTS7960 / L298N | Mengendalikan motor | **Wajib**, jangan langsung ke GPIO |
| Adaptor 12V 2A | Daya motor | Terpisah dari USB ESP32 |
| Resistor & kapasitor | Pembagi tegangan, filter | Lihat daftar di bawah |

---

## 2. Peta Pin ESP32

### Sensor Analog (ADC1 — wajib, bukan ADC2)

| Sensor | Signal | GPIO | Tipe |
|---|---|---|---|
| ZMPT101B | OUT | **GPIO 35** | Input ADC1_CH7 |
| ACS712 | OUT | **GPIO 34** | Input ADC1_CH6 (input-only) |

> **Kenapa ADC1?**
> GPIO ADC2 (0, 2, 4, 12–15, 25–27) **tidak bisa dipakai saat WiFi aktif**.
> Semua analog input harus di GPIO 32–39 (ADC1).
> GPIO 34–39 juga **hanya input**, tidak bisa jadi output.

### PZEM004T-V4 (UART2)

| PZEM pin | ke | GPIO | Catatan |
|---|---|---|---|
| TX | → | **GPIO 16** (RX2) | Pull-up 4.7kΩ ke 3.3V jika data tidak stabil |
| RX | ← | **GPIO 17** (TX2) | |
| VCC | — | **5V** | VCC PZEM = 5V, bukan 3.3V! |
| GND | — | **GND** | Wajib ground bersama |

> ⚠️ Jalur `Serial` bawaan dipakai untuk upload/monitor.
> PZEM **harus** pakai `Serial2` (GPIO 16/17). Jangan sampai bentrok!

### RTC DS3231 (I2C)

| DS3231 | ke | GPIO |
|---|---|---|
| VCC | — | **3.3V** (DS3231 aman di 3.3V) |
| GND | — | **GND** |
| SDA | — | **GPIO 21** |
| SCL | — | **GPIO 22** |

> Tambahkan **pull-up 4.7kΩ** SDA→3.3V dan SCL→3.3V jika modul tidak sudah punya.

### Motor RS555 (via driver)

| Fungsi | GPIO | Catatan |
|---|---|---|
| PWM | **GPIO 25** | Duty cycle 0–255 |
| DIR | **GPIO 26** | Arah putaran |
| EN | **GPIO 27** | **Active LOW** (LOW = boleh jalan) |

### Tombol Manual (opsional)

| Tombol | GPIO | Catatan |
|---|---|---|
| Feet | **GPIO 33** | Input-only, pakai `INPUT_PULLUP`, tekan ke GND |

### LED Status

| LED | GPIO |
|---|---|
| Onboard LED | **GPIO 2** |

---

## 3. Pin yang HARUS DIHINDARI

| GPIO | Alasan |
|---|---|
| **6, 7, 8, 9, 10, 11** | Terhubung ke flash internal — jangan dipakai |
| **0** | Boot mode (harus HIGH saat boot) |
| **12** | Memengaruhi tegangan flash (MTDI) |
| **15** | Boot mode, output debug saat boot |
| **2** | Boleh dipakai sebagai output, tapi jangan di-pull saat boot |
| **34–39** | Input-only |
| **ADC2 (0,2,4,12–15,25–27)** | Tidak bisa analog input saat WiFi aktif |

---

## 4. Rangkaian ZMPT101B (Pembagi Tegangan)

Modul ZMPT101B biasanya sudah punya resistor bawaan yang menghasilkan output ~0–3.3V untuk 250V AC.
**Jika modulmu sudah jadi board jadi pakai saja.** Kalau hanya IC zMPT101B, butuh:

```
AC mains ──┬── R1 (100kΩ) ──┬── R2 (10kΩ) ── GND
           │                 │
           │                 └──┴──> OUT ke GPIO 35
           │                       (+ kapasitor 100nF paralel ke R2)
           │
           └── ZMPT101B ──> OUT
```

Output ≈ `Vin × (R2 / (R1+R2))` = `Vin × 0.091`
Untuk 220V → tegangan output terlalu besar untuk GPIO 3.3V. Sesuaikan R1/R2 agar output sekitar 2.5V saat AC 250V.
Firmware melakukan **kalibrasi otomatis** terhadap PZEM004T, jadi selama rasio pembagi tegangan konsisten, angka akan akurat.

---

## 5. Rangkaian ACS712

Modul ACS712 sudah punya Gain (bias) 2.5V di VCC/2.
Output = `VCC/2 ± (arus × sensitivitas)`

| Varian | Sensitivitas | untuk motor RS555 12V (arus ~1–2A) |
|---|---|---|
| ACS712-5A | 185 mV/A | ✅ **paling cocok** |
| ACS712-30A | 100 mV/A | resolution kurang |
| ACS712-100A | 66 mV/A | terlalu kasar |

> Firmware mengkalibrasi **baseline** secara otomatis saat motor diam.
> Pastikan `ACS_SENSOR_MAX_AMP` dan `ACS_SENSITIVITY` di `config.h` sesuai modulmu.

---

## 6. Motor Driver

### Pilihan A — BTS7960 (paling kuat, direkomendasikan)

```
ESP32 GPIO 25 (PWM) ──→ RPWM
ESP32 GPIO 26 (DIR) ──→ RISP
ESP32 GPIO 27 (EN)  ──→ RST

12V+ ──→ motor Power+
12V- ──→ motor Power-

Motor terminal ──→ B+ dan B- driver
```

### Pilihan B — L298N (murah, sudah banyak di tangan)

```
ESP32 GPIO 25 (PWM) ──→ ENA
ESP32 GPIO 26 (DIR) ──→ IN1
ESP32 GPIO 27 (EN)  ──→ IN2

OUT1, OUT2 ──→ motor terminal
12V+ / GND  ──→ power input modul
GND modul ──→ GND ESP32 (WAJIB)
```

> ⚠️ **L298N punya drop voltage ~2V**, motor dapat tegangan ~10V dari 12V.
> Untuk RS555 ini masih jalan, tapi lebih ideal pakai MOSFET atau BTS7960.

### Pilihan C — MOSFET kanal-N + diody (paling sederhana)

```
GPIO 25 ──→ Gate MOSFET (IRF540N / logic level)
12V+ ──→ Motor ──→ Drain MOSFET
Source MOSFET ──→ GND
Motor ──→ Diody 1N5822 / 1N4007 (kathode ke +, anoda ke -)  [flyback]
```

---

## 7. DNS List Koneksi (Ringkasan)

```
ESP32                      Modul
-----                      -----
3V3  ───────────────────── DS3231 VCC
3V3  ───────────────────── ACS712 VCC
5V  ───────────────────── PZEM004T VCC
GND ────────────────────── semua GND (WAJIB satu titik)

GPIO 35 ─────────────────── ZMPT101B OUT
GPIO 34 ─────────────────── ACS712 OUT
GPIO 16 (RX2) ───────────── PZEM004T TX
GPIO 17 (TX2) ───────────── PZEM004T RX
GPIO 21 ─────────────────── DS3231 SDA
GPIO 22 ─────────────────── DS3231 SCL
GPIO 25 ─────────────────── Driver PWM
GPIO 26 ─────────────────── Driver DIR
GPIO 27 ─────────────────── Driver EN
GPIO 33 ─────────────────── Tombol manual (opsional)
GPIO 2  ─────────────────── LED onboard

220V AC ─────────────────── ZMPT101B (input) — HATI-HATI
220V AC ─────────────────── PZEM004T (input)
Adaptor 12V ─────────────── Motor / driver power
```

---

## 8. Konfigurasi Awal (`config.h`)

Sebelum upload, edit `firmware/config.h`:

```cpp
#define WIFI_SSID      "NamaWiFiRumahmu"
#define WIFI_PASSWORD  "PasswordWiFi"
#define SERVER_HOST    "192.168.1.3"    // IP laptop (cek dengan: ipconfig)
#define SERVER_PORT    8080
#define ACS_SENSOR_MAX_AMP 5.0f         // sesuai modul (5A/30A/100A)
#define ACS_SENSITIVITY  0.185f         // 5A: 0.185, 30A: 0.100, 100A: 0.066
```

Untuk jadwal 07:00/12:00/17:00, biarkan default. Takaran per slot bisa diubah dari dashboard.

---

## 9. Checklist Commissioning

1. ☐ Upload firmware, buka Serial Monitor (115200 baud)
2. ☐ Cek log `[WIFI] OK, IP = ...`
3. ☐ Cek `[RTC] Waktu: ...`
4. ☐ Cek nilai sensor realistic (ZMPT ~220V, ACS712 baseline ~1.65V)
5. ☐ Jalankan `run.bat` di laptop, buka `http://192.168.1.3:8080`
6. ☐ Pastikan dashboard menampilkan "ESP32 online"
7. ☐ Uji motor manual dengan tombol **Feed Sekarang**
8. ☐ Setel jadwal, tunggu slot berikutnya (atau ubah sementara ke menit depan untuk testing)
9. ☐ Kalau data tidak masuk: cek `SERVER_HOST` di `config.h` sudah sesuai IP laptop

---

## 10. Troubleshooting Cepat

| Gejala | Penyebab & Solusi |
|---|---|
| ZMPT baca 0V tapi AC nyala | R1/R2 salah. Firmware akan kalibrasi; cek Serial log `[CAL]` |
| ZMPT baca >250V | Gain terlalu besar, ganti R1 lebih besar |
| ACS712 selalu 0.00A | Motor tidak jalan / kabel terbalik / modul 100A dengan setting 5A |
| Motor tidak berputar | EN HIGH (aktif LOW), cek GPIO 27. PWM 0? Cek driver |
| Motor getar tapi tidak berputar | Baterai drop — ganti ke adaptor 12V 2A yang lebih baik |
| Motor berputar terus | DurationMillis overflow / tidak ada scheduler. Cek Serial log `[MOTOR]` |
| PZEM tidak terbaca | TX/RX terbalik, atau baud bukan 9600, atau VCC harus 5V |
| Dashboard "ESP32 offline" | `SERVER_HOST` salah, atau firewall laptop memblokir port 8080 |
| Dashboard tidak terbuka dari HP | HP & laptop harus di WiFi yang sama; firewall harus allow port 8080 |
| RTC selalu NULL | Baterai DS3231 habis, atau SDA/SCL terbalik |

---

*Documentasi ini bagian dari project Pelempar Pakan Ikan Otomatis.*
*Sensor: ZMPT101B · ACS712 · PZEM004T-V4 · RTC DS3231 · Motor RS555 12V*