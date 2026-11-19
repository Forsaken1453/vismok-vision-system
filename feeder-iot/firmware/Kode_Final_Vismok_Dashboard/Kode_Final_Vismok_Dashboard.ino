/*
  ================================================================
  SISTEM PELEMPAR PAKAN IKAN OTOMATIS BERBASIS ESP32 + RTC
  Dengan Monitoring Energi (PZEM-004T V3, ACS712 20A, ZMPT101B)
  Terintegrasi Telegram Bot (IoT)

  VISMOK - Fish Feeder IoT (Forsaken1453)
  ================================================================

  LIBRARY YANG DIBUTUHKAN (install lewat Arduino IDE > Library Manager):
  - RTClib                 (by Adafruit)
  - LiquidCrystal I2C       (by Frank de Brabander / Marco Schwartz)
  - PZEM004Tv30             (by Jakub Mandula)
  - UniversalTelegramBot    (by Brian Lough)
  - ArduinoJson             (by Benoit Blanchon) - versi 6.x
  - ESP32Servo              (by Kevin Harrington, John K. Bennett)

  BOARD: pilih "ESP32 Dev Module" di Tools > Board

  CATATAN PENTING SEBELUM UPLOAD PERTAMA KALI:
  1. Isi WIFI_SSID, WIFI_PASSWORD, BOT_TOKEN, CHAT_ID di bawah.
  2. Jam RTC diset OTOMATIS dari internet (NTP) dalam zona WIB (UTC+7)
     setiap kali ESP32 menyala dan terhubung WiFi, lalu disinkron ulang
     tiap 24 jam. Tidak perlu upload ulang untuk set jam. Jam disimpan di
     DS3231 dalam WIB, jadi jadwal pakan langsung memakai jam WIB.
  3. Bot Telegram hanya menuruti chat yang ID-nya sama dengan CHAT_ID.
     Chat lain akan ditolak dan diberi tahu ID chat-nya.
     Agar muncul daftar perintah saat mengetik "/", kirim /setcommands ke
     @BotFather lalu tempel daftar perintah (lihat penjelasan dari asisten).
  4. Kalibrasi ulang ACS712_SENSITIVITY dan zmpt_calibration di lapangan
     dengan membandingkan ke multimeter / clamp meter asli.
  5. LCD yang dipakai 20x4 -> constructor lcd(alamat, 20, 4). Kalau layar
     masih blank/berkedip setelah ini, cek alamat I2C-nya (0x27 atau 0x3F)
     pakai I2C scanner, dan putar trimmer kontras di belakang modul backpack.
  ================================================================
*/

#include <Wire.h>
#include <RTClib.h>
#include <LiquidCrystal_I2C.h>
#include <PZEM004Tv30.h>
#include <ESP32Servo.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <UniversalTelegramBot.h>
#include <math.h>
#include <string.h>

// ---------------- KONFIGURASI WIFI & TELEGRAM ----------------
const char* WIFI_SSID     = "ISI_SSID_WIFI";
const char* WIFI_PASSWORD = "ISI_PASSWORD_WIFI";
const char* BOT_TOKEN     = "ISI_BOT_TOKEN_DARI_BOTFATHER";
const char* CHAT_ID       = "ISI_CHAT_ID_GRUP";

WiFiClientSecure secured_client;
UniversalTelegramBot bot(BOT_TOKEN, secured_client);
unsigned long lastTelegramCheck = 0;
const unsigned long TELEGRAM_CHECK_INTERVAL = 1000; // cek pesan masuk tiap 1 detik

// Ganti alamat IP dan route sesuai server API dashboard.
const char* DASHBOARD_URL = "http://10.192.20.106:8080/api/ingest";
const unsigned long DASHBOARD_INTERVAL = 5000;
unsigned long lastDashboardPost = 0;
bool dashboardAutoFeed = true;

// ---------------- PIN DEFINISI ----------------
// L298N Motor Driver
#define PIN_ENA 25
#define PIN_IN1 26
#define PIN_IN2 27

// Servo SG90 (katup pakan) - kabel sinyal (oranye/kuning)
// Daya servo (merah) wajib dari rel 5V buck/LM2596, BUKAN dari pin 5V ESP32
#define PIN_SERVO 18

// Sensor arus & tegangan analog
#define PIN_ACS712   34  // ADC1_CH6
#define PIN_ZMPT101B 35  // ADC1_CH7

// PZEM-004T V3 (pakai Serial2 hardware)
#define PZEM_RX_PIN 16   // ke pin TX PZEM
#define PZEM_TX_PIN 17   // ke pin RX PZEM

// ---------------- OBJEK MODULE ----------------
RTC_DS3231 rtc;
LiquidCrystal_I2C lcd(0x27, 20, 4);  // <-- DIPERBAIKI: LCD 20x4, sebelumnya 16x2
PZEM004Tv30 pzem(Serial2, PZEM_RX_PIN, PZEM_TX_PIN);
Servo servoPakan;

// Sudut servo katup pakan (derajat). Sesuaikan dengan mekanik katup kalian:
// putar servo pelan-pelan sampai katup benar-benar menutup rapat / membuka penuh.
const int SERVO_TUTUP = 0;
const int SERVO_BUKA  = 90;

// ---------------- JADWAL PEMBERIAN PAKAN ----------------
// Silakan ubah jam/menit/durasi sesuai hasil kalibrasi mekanik pelempar
struct JadwalPakan {
  int jam;
  int menit;
  int durasiMotor; // detik, lama motor menyala saat melempar pakan
};

JadwalPakan jadwal[] = {
  {7,  0, 3},   // 07:00 pagi
  {12, 0, 3},   // 12:00 siang
  {17, 0, 3}    // 17:00 sore
};
const int JUMLAH_JADWAL = sizeof(jadwal) / sizeof(jadwal[0]);
int sudahDiberiMenitIni[10]; // flag anti-trigger-berulang dalam 1 menit yang sama

// ---------------- KALIBRASI SENSOR ----------------
// ACS712 20A -> sensitivitas 100 mV/A (untuk varian 5A pakai 0.185, 30A pakai 0.066)
const float ACS712_SENSITIVITY = 0.100;
float acs712_zeroVoltage = 2.5; // dikalibrasi otomatis saat setup() saat motor mati

// ZMPT101B -> faktor kalibrasi awal, WAJIB disesuaikan dengan multimeter di lapangan
float zmpt_calibration = 750.0;

// ---------------- SINKRON WAKTU (NTP -> RTC) ----------------
const long GMT_OFFSET_DETIK = 7 * 3600; // WIB = UTC+7 (tanpa daylight saving)
unsigned long lastNtpSync = 0;     // waktu percobaan sinkron terakhir (untuk jadwal 24 jam)
unsigned long lastNtpSukses = 0;   // waktu sinkron yang BERHASIL (untuk info /info)
bool ntpPernahSukses = false;

// ---------------- PENGATURAN BOT & RIWAYAT PAKAN ----------------
const int DURASI_MANUAL_DEFAULT = 3;            // detik, untuk /feed tanpa angka
const int DURASI_MANUAL_MAKS    = 10;           // batas aman /feed <detik>
const unsigned long COOLDOWN_MANUAL_MS = 30000; // jeda minimum antar pakan manual
unsigned long lastManualFeed = 0;
bool pernahManual = false;
unsigned long konfirmasiMs = 0;                 // waktu tombol konfirmasi dibuat
String riwayatPakanTerakhir = "Belum ada";
int jumlahPakanHariIni = 0;
int hariTercatat = -1;
bool rtcReady = false;

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22); // SDA, SCL

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Fish Feeder Ngawi");
  lcd.setCursor(0, 1);
  lcd.print("Booting...");

  pinMode(PIN_ENA, OUTPUT);
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  digitalWrite(PIN_ENA, HIGH); // aktifkan driver, motor full speed tiap kali IN1/IN2 aktif
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);

  // Servo katup pakan: pulsa 500-2400 us cocok untuk SG90
  servoPakan.setPeriodHertz(50);
  servoPakan.attach(PIN_SERVO, 500, 2400);
  servoPakan.write(SERVO_TUTUP); // katup tertutup saat boot
  delay(500);

  if (!rtc.begin()) {
    Serial.println("RTC tidak terdeteksi! Cek wiring SDA/SCL.");
    lcd.setCursor(0, 1);
    lcd.print("RTC ERROR!      ");
  } else {
    rtcReady = true;
  }
  for (int i = 0; i < JUMLAH_JADWAL; i++) sudahDiberiMenitIni[i] = 0;

  kalibrasiACS712(); // pastikan motor dalam keadaan mati saat boot

  connectWiFi();
  secured_client.setInsecure(); // supaya koneksi ke API Telegram tidak divalidasi sertifikat penuh

  // Set jam RTC (WIB) dari internet. Jika NTP gagal dan baterai RTC pernah habis/lepas,
  // pakai waktu kompilasi sebagai cadangan darurat (kurang akurat beberapa detik-menit).
  if (!sinkronRTCdariNTP() && rtc.lostPower()) {
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
    Serial.println("NTP gagal, RTC diset dari waktu kompilasi (perkiraan).");
  }

  String sapa = "🟢 <b>FISH FEEDER ONLINE</b>\n\n";
  sapa += "🕒 Jam RTC: " + formatWaktu(rtc.now()) + " WIB\n";
  sapa += "📡 WiFi: " + ikonSinyal(WiFi.RSSI()) + "\n";
  sapa += "🔜 Pakan berikutnya: " + infoJadwalBerikutnya(rtc.now()) + "\n\n";
  sapa += "Ketik /menu untuk membuka panel kontrol 👇";
  bot.sendMessage(CHAT_ID, sapa, "HTML");

  lcd.clear();
}

void loop() {
  DateTime now = rtc.now();
  cekJadwalPakan(now);
  updateLCD(now);

  // Sinkron ulang jam RTC dari NTP tiap 24 jam (jika WiFi tersambung)
  if (millis() - lastNtpSync > 86400000UL) {
    sinkronRTCdariNTP();
    lastNtpSync = millis(); // supaya tidak mencoba terus-menerus jika gagal
  }

  if (millis() - lastTelegramCheck > TELEGRAM_CHECK_INTERVAL) {
    cekPesanTelegram();
    lastTelegramCheck = millis();
  }

  if (millis() - lastDashboardPost >= DASHBOARD_INTERVAL) {
    lastDashboardPost = millis();
    kirimKeDashboard();
  }
}

// ---------------- FUNGSI DASHBOARD ----------------
String jsonFloat(float value, int decimals) {
  if (isnan(value) || isinf(value)) return "null";
  return String(value, decimals);
}

void prosesPerintahDashboard(const String& response) {
  DynamicJsonDocument doc(2048);
  DeserializationError error = deserializeJson(doc, response);
  if (error) {
    Serial.println("Respons perintah dashboard bukan JSON yang valid.");
    return;
  }

  JsonArray commands = doc["commands"].as<JsonArray>();
  for (JsonObject command : commands) {
    const char* type = command["type"] | "";

    if (strcmp(type, "FEED_NOW") == 0) {
      float takar = command["takar"] | 1.0f;
      if (!isfinite(takar) || takar < 0.2f || takar > 3.3f) {
        Serial.println("Perintah feed dashboard ditolak: takaran di luar batas.");
        continue;
      }

      if (pernahManual && millis() - lastManualFeed < COOLDOWN_MANUAL_MS) {
        Serial.println("Perintah feed dashboard ditolak: cooldown 30 detik.");
        continue;
      }

      int durasiDetik = constrain((int)lroundf(takar * 3.0f), 1,
                                  DURASI_MANUAL_MAKS);
      konfirmasiMs = 0;
      lastManualFeed = millis();
      pernahManual = true;
      beriPakan(durasiDetik, "Manual (Dashboard)");
    } else if (strcmp(type, "SET_SCHEDULE") == 0) {
      JsonArray slots = command["slots"].as<JsonArray>();
      if (slots.isNull() || slots.size() != JUMLAH_JADWAL) {
        Serial.println("Perintah jadwal dashboard ditolak: harus tepat 3 slot.");
        continue;
      }

      JadwalPakan updated[JUMLAH_JADWAL];
      bool valid = true;
      int index = 0;
      for (JsonObject slot : slots) {
        const char* timeValue = slot["time"] | "";
        float takar = slot["takar"] | 1.0f;
        if (strlen(timeValue) != 5 || timeValue[2] != ':' ||
            !isfinite(takar) || takar < 0.2f || takar > 3.3f) {
          valid = false;
          break;
        }

        char hourText[3] = {timeValue[0], timeValue[1], '\0'};
        char minuteText[3] = {timeValue[3], timeValue[4], '\0'};
        int hour = atoi(hourText);
        int minute = atoi(minuteText);
        if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
          valid = false;
          break;
        }

        updated[index].jam = hour;
        updated[index].menit = minute;
        updated[index].durasiMotor = constrain((int)lroundf(takar * 3.0f),
                                               1, DURASI_MANUAL_MAKS);
        index++;
      }

      if (!valid) {
        Serial.println("Perintah jadwal dashboard ditolak: data tidak valid.");
        continue;
      }

      for (int i = 0; i < JUMLAH_JADWAL; i++) {
        jadwal[i] = updated[i];
        sudahDiberiMenitIni[i] = 0;
      }
      dashboardAutoFeed = command["enabled"] | true;
      Serial.printf("Jadwal dashboard diterapkan; otomatis=%s\n",
                    dashboardAutoFeed ? "aktif" : "mati");
    }
  }
}

void kirimKeDashboard() {
  if (WiFi.status() != WL_CONNECTED) return;

  DateTime now = rtc.now();
  perbaruiHitunganHarian(now);

  String payload = "{";
  payload += "\"voltage\":" + jsonFloat(pzem.voltage(), 1) + ",";
  payload += "\"current\":" + jsonFloat(pzem.current(), 2) + ",";
  payload += "\"power\":" + jsonFloat(pzem.power(), 1) + ",";
  payload += "\"energy\":" + jsonFloat(pzem.energy(), 3) + ",";
  payload += "\"acs_current\":" + jsonFloat(bacaACS712(), 2) + ",";
  payload += "\"zmpt_voltage\":" + jsonFloat(bacaZMPT(), 1) + ",";
  payload += "\"feed_count_today\":" + String(jumlahPakanHariIni) + ",";
  payload += "\"time\":\"" + formatWaktu(now) + "\",";
  payload += "\"wifi_rssi\":" + String(WiFi.RSSI()) + ",";
  payload += "\"rtc_ok\":" + String(rtcReady ? "true" : "false") + ",";
  payload += "\"auto_feed\":" + String(dashboardAutoFeed ? "true" : "false") + ",";
  payload += "\"dashboard_control\":true,";
  payload += "\"uptime_ms\":" + String(millis()) + ",";
  payload += "\"free_heap\":" + String(ESP.getFreeHeap());
  payload += "}";

  WiFiClient client;
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(2000);

  if (!http.begin(client, DASHBOARD_URL)) {
    Serial.println("Gagal memulai koneksi ke dashboard.");
    return;
  }

  http.addHeader("Content-Type", "application/json");
  int status = http.POST(payload);
  Serial.printf("Dashboard HTTP status: %d\n", status);
  if (status == HTTP_CODE_OK) {
    prosesPerintahDashboard(http.getString());
  } else if (status < 0) {
    Serial.println(http.errorToString(status));
  } else {
    Serial.printf("Dashboard menolak telemetry (HTTP %d).\n", status);
  }
  http.end();
}

// ---------------- FUNGSI WIFI ----------------
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lcd.setCursor(0, 1);
  lcd.print("Connecting WiFi ");
  int percobaan = 0;
  while (WiFi.status() != WL_CONNECTED && percobaan < 40) {
    delay(500);
    Serial.print(".");
    percobaan++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi Connected: " + WiFi.localIP().toString());
  } else {
    Serial.println("Gagal konek WiFi, cek SSID/password.");
  }
}

// ---------------- FUNGSI WAKTU ----------------
// Format jam jadi HH:MM:SS (selalu 2 digit), contoh 07:05:09
String formatWaktu(DateTime t) {
  char buf[12];
  sprintf(buf, "%02d:%02d:%02d", t.hour(), t.minute(), t.second());
  return String(buf);
}

// Ambil waktu WIB dari internet (NTP) lalu tulis ke RTC DS3231.
// RTC menyimpan jam lokal WIB, jadi jadwal pakan langsung memakai jam WIB.
bool sinkronRTCdariNTP() {
  if (WiFi.status() != WL_CONNECTED) return false;

  configTime(GMT_OFFSET_DETIK, 0, "pool.ntp.org", "time.google.com");
  struct tm t;
  if (!getLocalTime(&t, 10000)) { // tunggu maksimal 10 detik
    Serial.println("Gagal ambil waktu dari NTP.");
    return false;
  }
  rtc.adjust(DateTime(t.tm_year + 1900, t.tm_mon + 1, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec));
  lastNtpSync = millis();
  lastNtpSukses = millis();
  ntpPernahSukses = true;
  Serial.println("RTC disinkron dari NTP (WIB): " + formatWaktu(rtc.now()));
  return true;
}

// ---------------- FUNGSI JADWAL & PAKAN ----------------
void cekJadwalPakan(DateTime now) {
  if (!dashboardAutoFeed) return;

  for (int i = 0; i < JUMLAH_JADWAL; i++) {
    if (now.hour() == jadwal[i].jam && now.minute() == jadwal[i].menit) {
      if (sudahDiberiMenitIni[i] == 0) {
        beriPakan(jadwal[i].durasiMotor, "Jadwal otomatis");
        sudahDiberiMenitIni[i] = 1;
      }
    } else {
      sudahDiberiMenitIni[i] = 0;
    }
  }
}

void beriPakan(int durasiDetik, String sumber) {
  Serial.println("Memberi pakan (" + sumber + ")...");
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Memberi Pakan...");

  unsigned long durasiMs = durasiDetik * 1000UL;
  unsigned long mulai = millis();

  // 1) Buka katup (servo) dan nyalakan motor DC pada saat yang sama
  servoPakan.write(SERVO_BUKA);
  digitalWrite(PIN_IN1, HIGH);
  digitalWrite(PIN_IN2, LOW);

  // 2) Tunggu sampai mendekati akhir, lalu ukur energi SAAT motor masih berputar
  //    (kalau diukur setelah motor mati, arus motor akan terbaca ~0 A).
  //    Pembacaan sensor butuh sekitar 0.5 detik; jika durasi pendek, ukur langsung.
  unsigned long tungguUkur = (durasiMs > 1500) ? (durasiMs - 1000) : 0;
  delay(tungguUkur);

  float arusACS712   = bacaACS712();
  float teganganZMPT = bacaZMPT();
  float teganganPZEM = pzem.voltage();
  float dayaPZEM     = pzem.power();
  float energiPZEM   = pzem.energy();

  // Habiskan sisa durasi supaya total motor menyala sesuai jadwal
  unsigned long terpakai = millis() - mulai;
  if (terpakai < durasiMs) delay(durasiMs - terpakai);

  // 3) Matikan motor dan tutup katup bersamaan
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
  servoPakan.write(SERVO_TUTUP);
  delay(500); // beri waktu servo kembali ke posisi tertutup

  lcd.clear();

  // Catat riwayat pakan
  DateTime now = rtc.now();
  perbaruiHitunganHarian(now);
  jumlahPakanHariIni++;
  riwayatPakanTerakhir = formatWaktu(now) + " WIB - " + escHTML(sumber);

  // Laporan ke Telegram
  String pesan = "✅ <b>PAKAN BERHASIL DIBERIKAN</b>\n\n";
  pesan += "🕒 Waktu: " + formatWaktu(now) + " WIB\n";
  pesan += "🔧 Mode: " + escHTML(sumber) + "\n";
  pesan += "⏱️ Durasi: " + String(durasiDetik) + " detik (motor + katup)\n";
  pesan += "🍽️ Pakan hari ini: " + String(jumlahPakanHariIni) + "x\n\n";
  pesan += "⚡ <b>Data Energi Saat Motor Berputar</b>\n";
  pesan += ikonTegangan(teganganPZEM) + " PZEM: " + fmtNilai(teganganPZEM, 1, "V") + " | " + fmtNilai(dayaPZEM, 1, "W") + "\n";
  pesan += "🔋 Energi total: " + fmtNilai(energiPZEM, 3, "kWh") + "\n";
  pesan += ikonTegangan(teganganZMPT) + " ZMPT101B: " + fmtNilai(teganganZMPT, 1, "V") + "\n";
  pesan += "🧲 Arus motor (ACS712): " + fmtNilai(arusACS712, 2, "A") + "\n\n";
  pesan += "🔜 Berikutnya: " + infoJadwalBerikutnya(now);

  String keyboard = "[[" + tombol("📊 Status", "/status") + "," + tombol("📋 Menu", "/menu") + "]]";
  bot.sendMessageWithInlineKeyboard(CHAT_ID, pesan, "HTML", keyboard);
}

// ---------------- FUNGSI SENSOR ----------------
void kalibrasiACS712() {
  long total = 0;
  for (int i = 0; i < 200; i++) {
    total += analogRead(PIN_ACS712);
    delay(2);
  }
  float avgRaw = total / 200.0;
  acs712_zeroVoltage = (avgRaw / 4095.0) * 3.3;
  Serial.println("Kalibrasi ACS712 selesai. Offset: " + String(acs712_zeroVoltage));
}

float bacaACS712() {
  int sampel = 500;
  float sumSquares = 0;
  for (int i = 0; i < sampel; i++) {
    int raw = analogRead(PIN_ACS712);
    float voltase = (raw / 4095.0) * 3.3;
    float selisih = voltase - acs712_zeroVoltage;
    sumSquares += selisih * selisih;
    delayMicroseconds(200);
  }
  float vrms = sqrt(sumSquares / sampel);
  return vrms / ACS712_SENSITIVITY;
}

float bacaZMPT() {
  long sampel = 1000;
  long total = 0;
  for (int i = 0; i < sampel; i++) {
    total += analogRead(PIN_ZMPT101B);
    delayMicroseconds(100);
  }
  float meanRaw = total / (float)sampel;

  float sumSquares = 0;
  for (int i = 0; i < sampel; i++) {
    int raw = analogRead(PIN_ZMPT101B);
    float selisih = raw - meanRaw;
    sumSquares += selisih * selisih;
    delayMicroseconds(100);
  }
  float vrmsADC = sqrt(sumSquares / sampel);
  return vrmsADC * (3.3 / 4095.0) * zmpt_calibration;
}

// ---------------- FUNGSI LCD ----------------
void updateLCD(DateTime now) {
  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate < 1000) return;
  lastUpdate = millis();

  char buf[17];
  sprintf(buf, "%02d:%02d:%02d %02d/%02d", now.hour(), now.minute(), now.second(), now.day(), now.month());
  lcd.setCursor(0, 0);
  lcd.print(buf);

  lcd.setCursor(0, 1);
  lcd.print("P:");
  lcd.print(pzem.power(), 0);
  lcd.print("W I:");
  lcd.print(bacaACS712(), 1);
  lcd.print("A   ");
}

// ---------------- FUNGSI TELEGRAM ----------------
// Semua pesan memakai parse_mode HTML (<b>tebal</b>) + emoji + tombol inline.

// Escape karakter khusus HTML (untuk nama pengguna dsb.)
String escHTML(String s) {
  s.replace("&", "&amp;");
  s.replace("<", "&lt;");
  s.replace(">", "&gt;");
  return s;
}

// Format angka + satuan; kalau sensor tidak terbaca (NaN) tampilkan peringatan
String fmtNilai(float v, int desimal, const char* satuan) {
  if (isnan(v)) return "❌ tidak terbaca";
  return String(v, desimal) + " " + satuan;
}

// Lampu indikator tegangan listrik PLN
String ikonTegangan(float v) {
  if (isnan(v)) return "⚪";
  if (v >= 200 && v <= 240) return "🟢";
  if (v >= 180 && v <= 250) return "🟡";
  return "🔴";
}

String ikonJam(int jam) {
  if (jam < 10) return "🌅";
  if (jam < 15) return "☀️";
  if (jam < 18) return "🌇";
  return "🌙";
}

String ikonSinyal(int rssi) {
  if (rssi >= -60) return "📶 Kuat";
  if (rssi >= -75) return "📶 Sedang";
  return "📶 Lemah";
}

String formatUptime() {
  unsigned long d = millis() / 1000UL;
  unsigned long hari = d / 86400UL;
  unsigned long jam = (d % 86400UL) / 3600UL;
  unsigned long menit = (d % 3600UL) / 60UL;
  String s = "";
  if (hari > 0) s += String(hari) + " hari ";
  s += String(jam) + " jam " + String(menit) + " menit";
  return s;
}

// Reset hitungan pakan harian saat pergantian hari
void perbaruiHitunganHarian(DateTime now) {
  if (now.day() != hariTercatat) {
    hariTercatat = now.day();
    jumlahPakanHariIni = 0;
  }
}

// Cari jadwal terdekat berikutnya, contoh: "12:00 (2 jam 15 menit lagi)"
String infoJadwalBerikutnya(DateTime now) {
  int sekarangMenit = now.hour() * 60 + now.minute();
  int terdekat = 24 * 60 + 1;
  int idx = -1;
  for (int i = 0; i < JUMLAH_JADWAL; i++) {
    int selisih = jadwal[i].jam * 60 + jadwal[i].menit - sekarangMenit;
    if (selisih <= 0) selisih += 24 * 60;
    if (selisih < terdekat) {
      terdekat = selisih;
      idx = i;
    }
  }
  if (idx < 0) return "-";
  char buf[64];
  sprintf(buf, "%02d:%02d (%d jam %d menit lagi)", jadwal[idx].jam, jadwal[idx].menit, terdekat / 60, terdekat % 60);
  return String(buf);
}

// Satu tombol inline: {"text":"...","callback_data":"..."}
String tombol(String teks, String data) {
  return "{\"text\":\"" + teks + "\",\"callback_data\":\"" + data + "\"}";
}

void kirimMenu(String chatId, String nama) {
  DateTime now = rtc.now();
  String pesan = "👋 Halo, <b>" + escHTML(nama) + "</b>!\n\n";
  pesan += "🐟 <b>FISH FEEDER IoT</b>\n";
  pesan += "Pelempar pakan ikan otomatis + monitoring energi\n\n";
  pesan += "🕒 " + formatWaktu(now) + " WIB\n";
  pesan += "🔜 Pakan berikutnya: " + infoJadwalBerikutnya(now) + "\n\n";
  pesan += "Pilih menu di bawah 👇";

  String keyboard = "[[" + tombol("🍽️ Beri Pakan Sekarang", "/feed") + "],"
                    "[" + tombol("📊 Status Energi", "/status") + "," + tombol("🕒 Jadwal", "/jadwal") + "],"
                    "[" + tombol("ℹ️ Info Sistem", "/info") + "," + tombol("❓ Bantuan", "/help") + "]]";
  bot.sendMessageWithInlineKeyboard(chatId, pesan, "HTML", keyboard);
}

void kirimBantuan(String chatId) {
  String pesan = "❓ <b>DAFTAR PERINTAH</b>\n\n";
  pesan += "📋 /menu - menu utama bertombol\n";
  pesan += "🍽️ /feed - beri pakan (default " + String(DURASI_MANUAL_DEFAULT) + " detik)\n";
  pesan += "🍽️ /feed 5 - beri pakan 5 detik (maks " + String(DURASI_MANUAL_MAKS) + ")\n";
  pesan += "📊 /status - tegangan, arus, daya, energi\n";
  pesan += "🕒 /jadwal - jadwal pakan harian\n";
  pesan += "ℹ️ /info - info sistem (WiFi, jam RTC, uptime)\n";
  pesan += "❓ /help - bantuan ini\n\n";
  pesan += "💡 Pakan manual meminta konfirmasi dulu supaya tidak kepencet.";
  bot.sendMessage(chatId, pesan, "HTML");
}

void kirimJadwal(String chatId) {
  DateTime now = rtc.now();
  perbaruiHitunganHarian(now);
  String pesan = "🕒 <b>JADWAL PAKAN HARIAN</b> (WIB)\n\n";
  for (int j = 0; j < JUMLAH_JADWAL; j++) {
    char baris[48];
    sprintf(baris, "%02d:%02d  -  %d detik", jadwal[j].jam, jadwal[j].menit, jadwal[j].durasiMotor);
    pesan += ikonJam(jadwal[j].jam) + " " + String(baris) + "\n";
  }
  pesan += "\n🔜 Berikutnya: <b>" + infoJadwalBerikutnya(now) + "</b>\n";
  pesan += "🍽️ Pakan hari ini: " + String(jumlahPakanHariIni) + "x\n";
  pesan += "📝 Terakhir: " + riwayatPakanTerakhir;

  String keyboard = "[[" + tombol("🍽️ Beri Pakan", "/feed") + "," + tombol("📋 Menu", "/menu") + "]]";
  bot.sendMessageWithInlineKeyboard(chatId, pesan, "HTML", keyboard);
}

void kirimStatus(String chatId) {
  DateTime now = rtc.now();
  perbaruiHitunganHarian(now);

  float vP  = pzem.voltage();
  float iP  = pzem.current();
  float pP  = pzem.power();
  float eP  = pzem.energy();
  float fP  = pzem.frequency();
  float pfP = pzem.pf();
  float vZ  = bacaZMPT();
  float iA  = bacaACS712();

  String pesan = "📊 <b>STATUS FISH FEEDER</b>\n";
  pesan += "🕒 " + formatWaktu(now) + " WIB\n\n";
  pesan += "⚡ <b>Energi AC (PZEM-004T)</b>\n";
  pesan += ikonTegangan(vP) + " Tegangan: " + fmtNilai(vP, 1, "V") + "\n";
  pesan += "🔌 Arus: " + fmtNilai(iP, 2, "A") + "\n";
  pesan += "💡 Daya: " + fmtNilai(pP, 1, "W") + "\n";
  pesan += "🔋 Energi: " + fmtNilai(eP, 3, "kWh") + "\n";
  pesan += "〰️ Frekuensi: " + fmtNilai(fP, 1, "Hz") + "\n";
  pesan += "📐 Faktor daya: " + fmtNilai(pfP, 2, "") + "\n\n";
  pesan += "🔬 <b>Sensor Pembanding</b>\n";
  pesan += ikonTegangan(vZ) + " ZMPT101B: " + fmtNilai(vZ, 1, "V") + "\n";
  pesan += "🧲 ACS712 (jalur 12V): " + fmtNilai(iA, 2, "A") + "\n\n";
  pesan += "🍽️ <b>Pakan</b>\n";
  pesan += "Hari ini: " + String(jumlahPakanHariIni) + "x\n";
  pesan += "Terakhir: " + riwayatPakanTerakhir + "\n";
  pesan += "Berikutnya: " + infoJadwalBerikutnya(now);

  String keyboard = "[[" + tombol("🔄 Segarkan", "/status") + "," + tombol("📋 Menu", "/menu") + "]]";
  bot.sendMessageWithInlineKeyboard(chatId, pesan, "HTML", keyboard);
}

void kirimInfo(String chatId) {
  DateTime now = rtc.now();
  char tgl[16];
  sprintf(tgl, "%02d/%02d/%04d", now.day(), now.month(), now.year());
  int rssi = WiFi.RSSI();

  String pesan = "ℹ️ <b>INFO SISTEM</b>\n\n";
  pesan += "🕒 Jam RTC: " + formatWaktu(now) + " WIB\n";
  pesan += "📅 Tanggal: " + String(tgl) + "\n";
  if (ntpPernahSukses) {
    unsigned long jamLalu = (millis() - lastNtpSukses) / 3600000UL;
    pesan += "🔄 Sinkron NTP: " + String(jamLalu) + " jam lalu\n";
  } else {
    pesan += "🔄 Sinkron NTP: belum berhasil\n";
  }
  pesan += "📡 WiFi: " + escHTML(WiFi.SSID()) + " (" + ikonSinyal(rssi) + ", " + String(rssi) + " dBm)\n";
  pesan += "🌐 IP: " + WiFi.localIP().toString() + "\n";
  pesan += "⏱️ Aktif sejak boot: " + formatUptime() + "\n";
  pesan += "🧠 Memori bebas: " + String(ESP.getFreeHeap() / 1024) + " KB";

  String keyboard = "[[" + tombol("📋 Menu", "/menu") + "]]";
  bot.sendMessageWithInlineKeyboard(chatId, pesan, "HTML", keyboard);
}

// Minta konfirmasi sebelum motor + servo jalan (anti kepencet)
void tanyaKonfirmasiPakan(String chatId, int detik) {
  konfirmasiMs = millis();
  String pesan = "🍽️ <b>KONFIRMASI PEMBERIAN PAKAN</b>\n\n";
  pesan += "Motor DC + servo katup akan aktif selama <b>" + String(detik) + " detik</b>.\n";
  pesan += "Lanjutkan? (berlaku 60 detik)";
  String keyboard = "[[" + tombol("✅ Ya, beri pakan", "/yes" + String(detik)) + "," + tombol("❌ Batal", "/batal") + "]]";
  bot.sendMessageWithInlineKeyboard(chatId, pesan, "HTML", keyboard);
}

void eksekusiPakanManual(String chatId, int detik, String nama) {
  if (konfirmasiMs == 0 || millis() - konfirmasiMs > 60000UL) {
    bot.sendMessage(chatId, "⌛ Konfirmasi sudah kedaluwarsa. Ketik /feed lagi ya.", "");
    return;
  }
  if (pernahManual && millis() - lastManualFeed < COOLDOWN_MANUAL_MS) {
    int sisa = (COOLDOWN_MANUAL_MS - (millis() - lastManualFeed)) / 1000UL + 1;
    bot.sendMessage(chatId, "⏳ Tunggu <b>" + String(sisa) + " detik</b> lagi sebelum pakan manual berikutnya.", "HTML");
    return;
  }
  konfirmasiMs = 0; // satu konfirmasi hanya berlaku sekali
  lastManualFeed = millis();
  pernahManual = true;
  bot.sendMessage(chatId, "🚀 Memulai pemberian pakan <b>" + String(detik) + " detik</b>...\n⚙️ Motor DC + servo katup aktif", "HTML");
  beriPakan(detik, "Manual (Telegram) oleh " + nama);
}

// Satu pintu untuk semua perintah teks maupun tombol inline
void prosesPerintah(String teks, String chatId, String nama) {
  teks.trim();
  if (!teks.startsWith("/")) return; // abaikan obrolan biasa (terutama di grup)

  String kata = teks;
  String arg = "";
  int sp = teks.indexOf(' ');
  if (sp > 0) {
    kata = teks.substring(0, sp);
    arg = teks.substring(sp + 1);
    arg.trim();
  }
  int at = kata.indexOf('@'); // buang akhiran @namabot dari perintah di grup
  if (at > 0) kata = kata.substring(0, at);
  kata.toLowerCase();

  // Hanya chat yang terdaftar (CHAT_ID) yang boleh mengendalikan alat
  if (chatId != String(CHAT_ID)) {
    String pesan = "⛔ <b>Akses ditolak</b>\nChat ini belum terdaftar untuk mengendalikan alat.\n\n";
    pesan += "🆔 ID chat ini: <code>" + chatId + "</code>";
    bot.sendMessage(chatId, pesan, "HTML");
    return;
  }

  if (kata == "/start" || kata == "/menu") {
    kirimMenu(chatId, nama);
  } else if (kata == "/feed" || kata == "/feednow") {
    int d = (arg.length() > 0) ? arg.toInt() : DURASI_MANUAL_DEFAULT;
    if (d < 1 || d > DURASI_MANUAL_MAKS) {
      bot.sendMessage(chatId, "⚠️ Durasi harus 1 sampai " + String(DURASI_MANUAL_MAKS) + " detik. Contoh: /feed 5", "");
    } else {
      tanyaKonfirmasiPakan(chatId, d);
    }
  } else if (kata.startsWith("/yes")) {
    int d = kata.substring(4).toInt();
    if (d < 1 || d > DURASI_MANUAL_MAKS) d = DURASI_MANUAL_DEFAULT;
    eksekusiPakanManual(chatId, d, nama);
  } else if (kata == "/batal") {
    konfirmasiMs = 0;
    bot.sendMessage(chatId, "❎ Pemberian pakan dibatalkan.", "");
  } else if (kata == "/status") {
    kirimStatus(chatId);
  } else if (kata == "/jadwal") {
    kirimJadwal(chatId);
  } else if (kata == "/info") {
    kirimInfo(chatId);
  } else if (kata == "/help") {
    kirimBantuan(chatId);
  } else {
    bot.sendMessage(chatId, "🤔 Perintah tidak dikenali. Ketik /menu atau /help ya.", "");
  }
}

void cekPesanTelegram() {
  int jumlahPesan = bot.getUpdates(bot.last_message_received + 1);
  while (jumlahPesan) {
    for (int i = 0; i < jumlahPesan; i++) {
      String teks = bot.messages[i].text;
      String chatId = bot.messages[i].chat_id;
      String nama = bot.messages[i].from_name;
      if (nama == "") nama = "Teman";
      prosesPerintah(teks, chatId, nama);
    }
    jumlahPesan = bot.getUpdates(bot.last_message_received + 1);
  }
}
