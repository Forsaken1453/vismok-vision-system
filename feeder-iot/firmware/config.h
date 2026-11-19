/* =====================================================================
 * config.h - Peta pin & konstanta firmware Pelempar Pakan Ikan
 *
 * Board  : ESP32 DevKit V4 (38-pin, ESP32-WROOM-32)
 * Sensor : ZMPT101B (AC voltase), ACS712 (arus DC motor), PZEM004T-V4
 * RTC    : DS3231
 * Aktuator: Motor DC 12V RS555 via driver MOSFET/BTS7960/L298N
 *
 * PENTING: pin ADC2 (GPIO 0,2,4,12,13,14,15,25,26,27) TIDAK boleh dipakai
 * untuk analog input ketika WiFi aktif. Semua sensor analog di sini
 * memakai ADC1 (GPIO 32-39) agar tidak konflik.
 * ===================================================================== */
#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

/* ---------------- WiFi ---------------- */
#define WIFI_SSID      "GANTI_SSID_RUMAH"
#define WIFI_PASSWORD  "GANTI_PASSWORD_RUMAH"
#define WIFI_TIMEOUT_MS 15000UL

/* ---------------- Server laptop (Flask) ----------------
 * Dapatkan IP laptop: buka CMD di laptop, ketik "ipconfig"
 * Contoh: 192.168.1.3  ->  ESP32 akan POST ke http://192.168.1.3:8080
 * Ubah juga jika IP laptop berubah (DHCP). */
#define SERVER_HOST    "192.168.1.3"
#define SERVER_PORT    8080

/* ---------------- Sensor analog ---------------- */
#define PIN_ZMPT101B   35   // ADC1_CH7 - output ZMPT101B
#define PIN_ACS712     34   // ADC1_CH6 - output ACS712 (input only)

/* ZMPT101B kalibrasi ----------------------------------------------
 * ZMPT101B mengikuti tegangan mains, jadi kalibrasi dilakukan RUNTIME
 * terhadap PZEM004T (yang optocoupler-isolated dan akurat).
 *_buf kosong = kalibrasi otomatis.                             */
#define ZMPT_AUTO_CALIBRATE true
#define ZMPT_CAL_MANUAL 220.0f   // dipakai bila auto=false
#define ZMPT_CAL_SAMPLES 30      // jumlah sampel rata-rata saat kalibrasi

/* ACS712 ----------------------------------------------------------
 * Varisensor: 5A / 30A / 100A. Sesuaikan dengan modulmu.
 *   ACS712-5A  : sensitivitas 185 mV/A
 *   ACS712-30A : sensitivitas 100 mV/A
 *   ACS712-100A: sensitivitas  66 mV/A                            */
#define ACS_SENSOR_MAX_AMP 5.0f
#define ACS_SENSITIVITY  0.185f   // V/A  (untuk 5A)
#define ACS_RAW_MIN      1900     // ~2.5V baseline (12-bit)
#define ACS_RAW_MAX      3300
#define ACS_FILTER_ALPHA  0.25f   // exponential moving average

/* PZEM004T-V4 (UART2) */
#define PIN_PZEM_RX     16        // ESP32 RX2 <- PZEM TX
#define PIN_PZEM_TX     17        // ESP32 TX2 -> PZEM RX
#define PZEM_BAUD       9600
#define PZEM_POLL_MS    1000      // interval baca PZEM
#define AC_PRESENT_MIN_V 20.0f   // < ini dianggap AC mati

/* ---------------- RTC DS3231 (I2C) ---------------- */
#define PIN_SDA         21
#define PIN_SCL         22
#define RTC_ADDR        0x68

/* ---------------- Motor RS555 12V ---------------- */
#define PIN_MOTOR_PWM   25        // PWM  -> driver PWM input
#define PIN_MOTOR_DIR   26        // arah  -> driver IN1
#define PIN_MOTOR_EN    27        // aktif LOW = motor boleh jalan
#define MOTOR_PWM_MAX   255       // duty cycle penuh
#define MOTOR_PWM_SOFT  200       // duty cycle normal (hindari over-current di awal)

/* ---------------- Tombol manual (opsional) ---------------- */
#define PIN_BTN_MANUAL  33        // GND -> GPIO (INPUT_PULLUP)
#define BTN_DEBOUNCE_MS 50

/* ---------------- LED status ---------------- */
#define PIN_LED         2         // onboard LED ESP32

/* ---------------- Jadwal default ----------------
 * Format: "HH:MM"
 * Takaran feeds: 1 takar = MOTOR_BASE_SECOND detik putar motor.
 * Durasi motor   = MOTOR_BASE_SECOND x takaran
 */
#define DEFAULT_SLOT_1   "07:00"
#define DEFAULT_SLOT_2   "12:00"
#define DEFAULT_SLOT_3   "17:00"
#define DEFAULT_TAKAR    1.0

/* 1 takar = 3 detik, sesuai kebutuhan awal */
#define MOTOR_BASE_SECOND 3.0f
#define MAX_TAKAR        5.0f
#define MIN_TAKAR        0.2f

/* Grace period sebelum ditandai SCHEDULE_MISSED (detik) */
#define SCHEDULE_MISS_GRACE 30

/* Motor dianggap gagal kalau peak arus < ini (A) */
#define MOTOR_MIN_PEAK_CURRENT 0.15f

/* Deteksi AC dropout: ZMPT baca ~0 sementara PZEM normal */
#define ZMPT_OUTLIER_MIN_V 5.0f
#define ZMPT_OUTLIER_MAX_V 300.0f

/* ---------------- Pengiriman data ke Flask ---------------- */
#define TELEMETRY_INTERVAL_MS 1000UL   // push tiap 1 detik
#define HTTP_PUSH_TIMEOUT_MS  1500
#define HTTP_RETRY_MS         2000     // retry jika gagal

/* ---------------- Debug ---------------- */
#define DEBUG_SERIAL     true
#define SERIAL_BAUD      115200

#endif // CONFIG_H