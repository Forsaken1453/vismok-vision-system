/* =====================================================================
 *  FISH FEEDER - GABUNGAN (VISMOK + Dashboard Web)
 *  =====================================================================
 *  Kode ini adalah sketsa VISMOK yang DIPERLUAS agar bisa
 *  tampil realtime di dashboard web (Flask di laptop), tanpa menghilangkan
 *  fitur lama:
 *
 *  [TETAP ADA - dari kode kamu]
 *  - LCD 20x4 I2C (0x27)
 *  - Telegram bot: /start /status /jadwal /feednow
 *  - Jadwal 07:00 / 12:00 / 17:00 (RTC DS3231)
 *  - PZEM004T V3 (library PZEM004Tv30), ACS712, ZMPT101B
 *  - Motor DC 12V via L298N (ENA/IN1/IN2)
 *
 *  [BARU - integrasi dashboard]
 *  - POST /api/ingest ke laptop tiap 1 detik -> grafik & gauge web
 *  - Menerima perintah dari web: FEED_NOW, SET_SCHEDULE (termasuk
 *    tombol "Feed Sekarang" dan toggle "Mode otomatis" di browser)
 *  - Alert "pelempar gagal" -> muncul di web + dikirim ke Telegram
 *  - Motor non-blocking: selama motor berputar, Telegram/LCD/web tetap
 *    hidup (paket masih terkirim, tombol tetap respons)
 *
 *  LIBRARY (Arduino IDE > Library Manager):
 *  - RTClib            (Adafruit)
 *  - LiquidCrystal I2C (Frank de Brabander)
 *  - PZEM004Tv30       (Jakub Mandula)   <- V3, sesuai alatmu
 *  - UniversalTelegramBot (Brian Lough)
 *  - ArduinoJson       6.21.x  <- PENTING: versi 6, BUKAN 7
 *                        (kalau 7.x terpasang, Tools > Library Manager,
 *                         pilih versi 6.21.5)
 *  BOARD: "ESP32 Dev Module"
 *
 *  SEBELUM UPLOAD:
 *  1. Cek WIFI_SSID / WIFI_PASSWORD / SERVER_HOST di bawah.
 *     SERVER_HOST = IP laptop (jalankan run.bat, IP tampil di banner,
 *     atau ketik "ipconfig" di CMD). Saat ini: 192.168.1.6
 *  2. Jika IP laptop berubah lagi (DHCP), update SERVER_HOST lalu
 *     upload ulang. Saran: set static lease di router biar tetap.
 *  3. L298N: ENA dipakai HIGH penuh (full speed), IN1/IN2 arah putaran.
 *  ===================================================================== */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <RTClib.h>
#include <LiquidCrystal_I2C.h>
#include <PZEM004Tv30.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>
#include <ArduinoJson.h>
#include <math.h>

/* ================= KONFIG (edit bagian ini saja) ================= */
const char* WIFI_SSID     = "Awaimoet";
const char* WIFI_PASSWORD = "ISI_PASSWORD_WIFI";
const char* BOT_TOKEN     = "ISI_BOT_TOKEN_DARI_BOTFATHER";
const char* CHAT_ID       = "ISI_CHAT_ID_GRUP";

/* IP laptop yang menjalankan dashboard (run.bat) */
#define SERVER_HOST    "192.168.1.6"
#define SERVER_PORT    8080

/* ---- Pin (L298N, sesuai wiring alatmu) ---- */
#define PIN_ENA     25
#define PIN_IN1     26
#define PIN_IN2     27
#define PIN_ACS712   34
#define PIN_ZMPT101B 35
#define PIN_PZEM_RX  16    // ESP32 RX2 <- TX PZEM
#define PIN_PZEM_TX  17    // ESP32 TX2 -> RX PZEM
#define PIN_SDA      21
#define PIN_SCL      22

/* ---- Kalibrasi sensor ---- */
const float ACS712_SENSITIVITY = 0.100;   // ACS712 20A (mV/A = 100)
float zmpt_calibration = 750.0;           // WAJIB dikalibrasi dg multimeter

/* ---- Jadwal & takaran ---- */
#define JUMLAH_JADWAL   3
#define MOTOR_BASE_MS   3000.0f   // 1 takar = 3 detik
#define MIN_TAKAR       0.2f
#define MAX_TAKAR       5.0f
#define TAKAR_DEFAULT   1.0f

/* ---- Threshold alert ---- */
#define MOTOR_MIN_PEAK_A   0.15f   // peak arus di bawah ini = motor macet
#define AC_PRESENT_MIN_V   20.0f   // PZEM < ini = AC mati
#define SCHEDULE_MISS_MIN  2      // lewat n menit tanpa jalan = missed

/* ---- Interval ---- */
#define TELEMETRY_INTERVAL_MS  1000UL
#define TELEGRAM_CHECK_MS      3000UL   // TLS polling berat, 3 detik cukup
#define PZEM_POLL_MS           1000UL
#define LCD_INTERVAL_MS        1000UL
#define WIFI_WATCHDOG_MS       10000UL
#define HTTP_PUSH_TIMEOUT_MS   1500UL

/* ========================= OBJEK & STATE ========================= */
RTC_DS3231 rtc;
LiquidCrystal_I2C lcd(0x27, 20, 4);
PZEM004Tv30 pzem(Serial2, PIN_PZEM_RX, PIN_PZEM_TX);

WiFiClientSecure secured_client;
UniversalTelegramBot bot(BOT_TOKEN, secured_client);

struct Slot { uint8_t hh, mm; float takar; };
Slot slots[JUMLAH_JADWAL] = { {7, 0, 1.0f}, {12, 0, 1.0f}, {17, 0, 1.0f} };
bool  autoFeed = true;
bool  slotDone[JUMLAH_JADWAL] = { false, false, false };

/* Sensor */
float acs712_zeroVoltage = 2.5f;
float zmptVoltage = 0, zmptRawV = 0;
float pzV = 0, pzI = 0, pzP = 0, pzWh = 0, pzHz = 0, pzPF = 0;
bool  pzemOk = false;

/* Motor (non-blocking) */
bool     motorRunning = false;
uint32_t motorStartMs = 0, motorDurationMs = 0;
float    motorPeakI = 0, motorCurrentNow = 0, motorLastTakar = 0;
/* Catatan hasil terakhir utk laporan Telegram */
bool     motorLastOk = true;

/* RTC */
bool rtcOk = false;
DateTime rtcNow;

/* Alert firmware -> web + Telegram */
String  alertCode = "NONE", alertMessage = "";
uint32_t alertSince = 0;

/* Timing */
unsigned long lastTelemetry = 0, lastPzem = 0, lastTelegram = 0,
              lastLcd = 0, lastWifiCheck = 0, lastSensor = 0;

/* ======================= UTIL WAKTU / ALERT ====================== */
int minuteOfDay() {
  if (!rtcOk) return -1;
  return rtcNow.hour() * 60 + rtcNow.minute();
}

void raiseAlert(const char* code, const char* msg) {
  if (alertCode == code) return;
  alertCode = code; alertMessage = msg; alertSince = millis();
  Serial.printf("[ALERT] %s - %s\n", code, msg);
}

void clearAlert(const char* code) {
  if (alertCode == code) { alertCode = "NONE"; alertMessage = ""; alertSince = 0; }
}

/* ============================ TELEGRAM =========================== */
void botSend(const String& text) {
  if (WiFi.status() != WL_CONNECTED) return;
  bot.sendMessage(CHAT_ID, text, "");
}

/* ============================== WiFi ============================= */
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WIFI] Menghubungkan");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(400); Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WIFI] OK, IP: "); Serial.println(WiFi.localIP());
  } else {
    Serial.println("[WIFI] Gagal. Cek SSID/password.");
  }
}

/* =============================== RTC ============================= */
void setupRTC() {
  Wire.begin(PIN_SDA, PIN_SCL);
  if (!rtc.begin()) {
    Serial.println("[RTC] DS3231 tidak terdeteksi!");
    return;
  }
  rtcOk = true;
  if (rtc.lostPower()) {
    Serial.println("[RTC] Baterai lemah, set waktu kompilasi");
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }
  /* Sinkron NTP sekali saat WiFi nyambung (WIB) */
  if (WiFi.status() == WL_CONNECTED) {
    configTime(7 * 3600, 0, "id.pool.ntp.org", "pool.ntp.org");
    struct tm t;
    if (getLocalTime(&t, 4000)) {
      rtc.adjust(DateTime(t.tm_year + 1900, t.tm_mon + 1, t.tm_mday,
                          t.tm_hour, t.tm_min, t.tm_sec));
      Serial.println("[RTC] Disinkron dari NTP");
    }
  }
  rtcNow = rtc.now();
}

/* ============================ SENSOR ============================= */
/* RMS dengan 2 tahap, metode RMS dua tahap (akurat utk ZMPT). */
void bacaZMPT() {
  const int N = 1000;
  long total = 0;
  for (int i = 0; i < N; i++) { total += analogRead(PIN_ZMPT101B); delayMicroseconds(100); }
  float meanRaw = total / (float)N;

  float sumSq = 0;
  for (int i = 0; i < N; i++) {
    float d = analogRead(PIN_ZMPT101B) - meanRaw;
    sumSq += d * d;
    delayMicroseconds(100);
  }
  float vrmsADC = sqrt(sumSq / N);
  zmptRawV   = (meanRaw / 4095.0f) * 3.3f;            // volt di pin
  zmptVoltage = vrmsADC * (3.3f / 4095.0f) * zmpt_calibration;
}

void bacaACS712() {
  const int N = 500;
  float sumSq = 0;
  for (int i = 0; i < N; i++) {
    float v = (analogRead(PIN_ACS712) / 4095.0f) * 3.3f;
    float d = v - acs712_zeroVoltage;
    sumSq += d * d;
    delayMicroseconds(200);
  }
  float vrms = sqrt(sumSq / N);
  motorCurrentNow = vrms / ACS712_SENSITIVITY;
}

/* Kalibrasi nol ACS712 saat motor mati (dipanggil di setup) */
void kalibrasiACS712() {
  long total = 0;
  for (int i = 0; i < 200; i++) { total += analogRead(PIN_ACS712); delay(2); }
  acs712_zeroVoltage = (total / 200.0f / 4095.0f) * 3.3f;
  Serial.printf("[CAL] ACS712 offset: %.3f V\n", acs712_zeroVoltage);
}

void bacaPZEM() {
  float v = pzem.voltage();
  pzemOk = !isnan(v) && v > 0;
  if (pzemOk) {
    pzV  = v;
    pzI  = pzem.current();
    pzP  = pzem.power();
    pzWh = pzem.energy() * 1000.0f;   // kWh -> Wh utk dashboard
    pzHz = pzem.frequency();
    pzPF = pzem.pf();
  }
}

/* Baca cepat tiap iterasi loop: arus instan + peak saat motor jalan,
 * baseline saat idle. Non-blocking, ~0.1 ms. */
void fastCurrentSample() {
  int raw = analogRead(PIN_ACS712);
  float v = (raw / 4095.0f) * 3.3f;
  float a = fabs((v - acs712_zeroVoltage) / ACS712_SENSITIVITY);
  if (motorRunning) {
    motorCurrentNow = a;
    if (a > motorPeakI) motorPeakI = a;
  }
}

/* ============================= MOTOR ============================= */
/* Non-blocking: motor jalan via state machine, loop tetap berputar. */
void startMotor(float takar) {
  if (motorRunning) return;
  takar = constrain(takar, MIN_TAKAR, MAX_TAKAR);
  motorRunning    = true;
  motorStartMs    = millis();
  motorDurationMs = (uint32_t)(MOTOR_BASE_MS * takar);
  motorPeakI      = 0;
  motorLastTakar  = takar;
  motorLastOk     = true;

  digitalWrite(PIN_ENA, HIGH);
  digitalWrite(PIN_IN1, HIGH);
  digitalWrite(PIN_IN2, LOW);
  Serial.printf("[MOTOR] Start %.2f takar = %lu ms\n", takar, motorDurationMs);
}

void stopMotor() {
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_ENA, HIGH);
  motorRunning = false;

  if (motorPeakI < MOTOR_MIN_PEAK_A) {
    motorLastOk = false;
    raiseAlert("MOTOR_NO_CURRENT",
               "Pelempar gagal! Motor berputar tapi arus tidak terdeteksi (mekanik macet / driver lepas)");
    botSend("⚠️ ALERT PELEMPAR GAGAL\n"
            "Motor jalan " + String(motorDurationMs / 1000.0f, 1) + " dtk,\n"
            "tapi peak arus hanya " + String(motorPeakI, 2) + " A.\n"
            "Kemungkinan: pakan macet / kopi geter lepas / L298N mati.");
    Serial.printf("[MOTOR] GAGAL. Peak=%.3f A\n", motorPeakI);
  } else {
    motorLastOk = true;
    clearAlert("MOTOR_NO_CURRENT");
    Serial.printf("[MOTOR] OK. Peak=%.3f A\n", motorPeakI);
  }
}

void updateMotor() {
  if (motorRunning && millis() - motorStartMs >= motorDurationMs) stopMotor();
}

/* ============================ JADWAL ============================= */
void updateSchedule() {
  if (!rtcOk) return;
  int mnow = minuteOfDay();

  /* reset harian tepat tengah malam */
  if (rtcNow.hour() == 0 && rtcNow.minute() == 0) {
    for (int i = 0; i < JUMLAH_JADWAL; i++) slotDone[i] = false;
  }

  int slotMinute[JUMLAH_JADWAL];
  for (int i = 0; i < JUMLAH_JADWAL; i++) slotMinute[i] = slots[i].hh * 60 + slots[i].mm;

  for (int i = 0; i < JUMLAH_JADWAL; i++) {
    if (slotDone[i]) continue;

    if (mnow >= slotMinute[i] && mnow < slotMinute[i] + SCHEDULE_MISS_MIN) {
      /* dalam jendela jadwal: jalan */
      if (!motorRunning) {
        slotDone[i] = true;
        Serial.printf("[SCHED] Slot %d %02d:%02d, %.1f takar\n",
                      i, slots[i].hh, slots[i].mm, slots[i].takar);
        startMotor(slots[i].takar);
        botSend("🍚 Pakan diberikan (jadwal " + String(slots[i].hh) + ":" +
                (slots[i].mm < 10 ? "0" : "") + String(slots[i].mm) +
                "), " + String(slots[i].takar, 1) + " takar.");
      }
    } else if (mnow >= slotMinute[i] + SCHEDULE_MISS_MIN) {
      /* terlewat (mis. ESP restart di menit jadwal) */
      slotDone[i] = true;
      raiseAlert("SCHEDULE_MISSED", "Jadwal terlewat tanpa eksekusi");
    }
  }
}

int nextSlotIndex() {
  if (!rtcOk) return -1;
  int mnow = minuteOfDay(), best = -1, bestD = 999999;
  for (int i = 0; i < JUMLAH_JADWAL; i++) {
    int d = slots[i].hh * 60 + slots[i].mm - mnow;
    if (d <= 0) d += 1440;
    if (d < bestD) { bestD = d; best = i; }
  }
  return best;
}

/* ========================= PUSH + PERINTAH ======================= */
void handleCommands(const String& body) {
  DynamicJsonDocument resp(2048);
  if (deserializeJson(resp, body) != DeserializationError::Ok) return;

  JsonArray cmds = resp["commands"].as<JsonArray>();
  if (cmds.isNull()) return;

  for (JsonObject c : cmds) {
    const char* type = c["type"] | "";

    if (strcmp(type, "FEED_NOW") == 0) {
      float takar = c["takar"] | (double)TAKAR_DEFAULT;
      Serial.printf("[CMD] FEED_NOW %.2f takar (dari web)\n", takar);
      startMotor(takar);
      botSend("🍽️ Feed Now dari dashboard web: " + String(takar, 1) + " takar.");
    } else if (strcmp(type, "SET_SCHEDULE") == 0) {
      JsonArray arr = c["slots"].as<JsonArray>();
      int i = 0;
      for (JsonObject s : arr) {
        if (i >= JUMLAH_JADWAL) break;
        const char* t = s["time"] | "00:00";
        slots[i].hh = atoi(t);
        slots[i].mm = atoi(t + 3);
        slots[i].takar = s["takar"] | (double)1.0;
        slots[i].takar = constrain(slots[i].takar, MIN_TAKAR, MAX_TAKAR);
        i++;
      }
      autoFeed = c["enabled"] | (bool)true;
      for (int j = 0; j < JUMLAH_JADWAL; j++) slotDone[j] = false;
      Serial.printf("[CMD] SET_SCHEDULE: %d slot, auto=%d\n", i, autoFeed);
    }
  }
}

void pushTelemetry() {
  if (WiFi.status() != WL_CONNECTED) return;

  DynamicJsonDocument doc(2048);
  doc["device_id"] = "fish-feeder-01";
  doc["uptime_ms"] = (uint32_t)millis();
  doc["free_heap"] = ESP.getFreeHeap();
  doc["rssi"]      = WiFi.RSSI();

  /* waktu dari RTC */
  char ts[24];
  if (rtcOk) {
    sprintf(ts, "%04d-%02d-%02dT%02d:%02d:%02d",
            rtcNow.year(), rtcNow.month(), rtcNow.day(),
            rtcNow.hour(), rtcNow.minute(), rtcNow.second());
    doc["time"] = ts;
    doc["rtc_ok"] = true;
  } else {
    doc["time"] = "";
    doc["rtc_ok"] = false;
  }

  /* jadwal */
  doc["auto_feed"]       = autoFeed;
  doc["next_slot_index"] = nextSlotIndex();
  int nsi = doc["next_slot_index"];
  doc["secs_to_next"] = 0;
  if (nsi >= 0) {
    int mnow = minuteOfDay();
    int d = slots[nsi].hh * 60 + slots[nsi].mm - mnow;
    if (d <= 0) d += 1440;
    doc["secs_to_next"] = d * 60;
  }
  JsonArray sj = doc.createNestedArray("schedule");
  for (int i = 0; i < JUMLAH_JADWAL; i++) {
    JsonObject o = sj.createNestedObject();
    char hhmm[8];
    sprintf(hhmm, "%02d:%02d", slots[i].hh, slots[i].mm);
    o["time"]  = hhmm;
    o["takar"] = slots[i].takar;
  }

  /* motor */
  JsonObject mo = doc.createNestedObject("motor");
  mo["running"]      = motorRunning;
  mo["peak_current"] = motorPeakI;
  mo["last_takar"]   = motorLastTakar;
  mo["remaining_ms"] = motorRunning
      ? (uint32_t)(motorDurationMs - (millis() - motorStartMs)) : 0;

  /* sensor */
  JsonObject se = doc.createNestedObject("sensors");
  se["zmtp_voltage"]  = zmptVoltage;
  se["zmtp_raw"]      = zmptRawV;
  se["acs_baseline"]  = acs712_zeroVoltage;
  se["motor_current"] = motorCurrentNow;
  se["peak_current"]  = motorPeakI;
  se["ac_voltage"]    = pzemOk ? pzV : 0;
  se["ac_current"]    = pzemOk ? pzI : 0;
  se["power_w"]       = pzemOk ? pzP : 0;
  se["energy_wh"]     = pzemOk ? pzWh : 0;
  se["freq"]          = pzemOk ? pzHz : 0;
  se["power_factor"]  = pzemOk ? pzPF : 0;
  se["pzem_ok"]       = pzemOk;

  /* alert */
  JsonObject al = doc.createNestedObject("alert");
  al["code"]     = alertCode;
  al["message"]  = alertMessage;
  al["active"]   = (alertCode != "NONE");
  al["since_ms"] = alertSince;

  String body;
  serializeJson(doc, body);

  HTTPClient http;
  String url = String("http://") + SERVER_HOST + ":" + SERVER_PORT + "/api/ingest";
  if (!http.begin(url)) return;
  http.setTimeout(HTTP_PUSH_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);
  if (code == 200) {
    handleCommands(http.getString());
  } else {
    Serial.printf("[HTTP] push gagal: %d\n", code);
  }
  http.end();
}

/* ============================ TELEGRAM =========================== */
void cekPesanTelegram() {
  int n = bot.getUpdates(bot.last_message_received + 1);
  while (n) {
    for (int i = 0; i < n; i++) {
      String text = bot.messages[i].text;
      String chatId = bot.messages[i].chat_id;

      if (text == "/feednow") {
        startMotor(TAKAR_DEFAULT);
        bot.sendMessage(chatId, "🍚 Pakan diberikan (3 detik).", "");
      } else if (text == "/status") {
        String p = "🐟 Status Fish Feeder\n";
        p += "RTC : " + (rtcOk ? String("OK") : String("ERROR")) + "\n";
        if (rtcOk) {
          p += "Jam : " + String(rtcNow.hour()) + ":" +
               (rtcNow.minute() < 10 ? "0" : "") + String(rtcNow.minute()) + "\n";
        }
        p += "Auto: " + String(autoFeed ? "AKTIF" : "MATI") + "\n";
        p += "PZEM: " + String(pzV, 1) + "V / " + String(pzI, 2) + "A / " +
             String(pzP, 1) + "W\n";
        p += "ZMPT: " + String(zmptVoltage, 1) + " V\n";
        p += "Arus motor: " + String(motorCurrentNow, 2) + " A\n";
        p += "Motor: " + String(motorRunning ? "JALAN" : "IDLE") + "\n";
        p += "Alert: " + alertCode;
        bot.sendMessage(chatId, p, "");
      } else if (text == "/jadwal") {
        String p = "📅 Jadwal pakan:\n";
        for (int j = 0; j < JUMLAH_JADWAL; j++) {
          char b[40];
          sprintf(b, "%02d:%02d  %.1f takar (%d dtk)\n",
                  slots[j].hh, slots[j].mm, slots[j].takar,
                  (int)(MOTOR_BASE_MS * slots[j].takar / 1000.0f));
          p += b;
        }
        bot.sendMessage(chatId, p, "");
      } else if (text == "/start") {
        bot.sendMessage(chatId,
          "🐟 Fish Feeder Bot\n\n"
          "/feednow - beri pakan sekarang\n"
          "/status  - status sensor & motor\n"
          "/jadwal  - lihat jadwal\n\n"
          "Dashboard web: http://" SERVER_HOST ":" + String(SERVER_PORT), "");
      }
    }
    n = bot.getUpdates(bot.last_message_received + 1);
  }
}

/* ============================== LCD ============================== */
void updateLCD() {
  char l0[24], l1[24], l2[24], l3[24];   /* 20 kolom + ruang aman utk NUL */

  if (rtcOk) {
    sprintf(l0, "%02d:%02d:%02d  %02d/%02d    ",
            rtcNow.hour(), rtcNow.minute(), rtcNow.second(),
            rtcNow.day(), rtcNow.month());
  } else {
    strcpy(l0, "RTC ERROR!        ");
  }

  int pzi = (int)(pzP + 0.5f);
  sprintf(l1, "P:%4dW I:%4.2fA   ", pzi, motorCurrentNow);

  int nsi = nextSlotIndex();
  if (nsi >= 0 && rtcOk) {
    int mnow = minuteOfDay();
    int d = slots[nsi].hh * 60 + slots[nsi].mm - mnow;
    if (d <= 0) d += 1440;
    sprintf(l2, "Next %02d:%02d-%02d:%02d:%02d",
            slots[nsi].hh, slots[nsi].mm,
            d / 60, d % 60, 0);
  } else {
    strcpy(l2, "Next: ?            ");
  }

  if (alertCode != "NONE") {
    strncpy(l3, alertMessage.length() ? alertMessage.substring(0, 19).c_str()
                                      : alertCode.c_str(), 19);
    l3[19] = 0;
  } else if (motorRunning) {
    sprintf(l3, "MOTOR RUN %.1fs    ",
            (motorDurationMs - (millis() - motorStartMs)) / 1000.0f);
  } else {
    strcpy(l3, "Motor: siap        ");
  }

  lcd.setCursor(0, 0); lcd.print(l0);
  lcd.setCursor(0, 1); lcd.print(l1);
  lcd.setCursor(0, 2); lcd.print(l2);
  lcd.setCursor(0, 3); lcd.print(l3);
}

/* ============================== SETUP ============================ */
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n==== Fish Feeder (VISMOK + Dashboard Web) ====");

  pinMode(PIN_ENA, OUTPUT);
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  digitalWrite(PIN_ENA, HIGH);
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0); lcd.print("Fish Feeder IoT");
  lcd.setCursor(0, 1); lcd.print("Booting...");

  setupRTC();

  /* Motor HARUS mati saat kalibrasi ACS712 */
  kalibrasiACS712();

  connectWiFi();
  secured_client.setInsecure();
  botSend("🐟 Fish Feeder online - dashboard web aktif.");

  lcd.clear();
  Serial.println("[BOOT] Siap. Push tiap 1 dtk ke " SERVER_HOST);
}

/* ============================== LOOP ============================= */
void loop() {
  if (rtcOk) rtcNow = rtc.now();

  updateMotor();
  updateSchedule();
  fastCurrentSample();

  unsigned long now = millis();

  /* sensor penuh + PZEM tiap 1 detik (blocking ~0.5 dtk, wajar) */
  if (now - lastSensor >= PZEM_POLL_MS) {
    lastSensor = now;
    bacaZMPT();
    bacaACS712();

    if (now - lastPzem >= PZEM_POLL_MS) {
      lastPzem = now;
      bacaPZEM();
      if (pzemOk && pzV < AC_PRESENT_MIN_V)
        raiseAlert("NO_AC_POWER", "Daya AC tidak terdeteksi (PZEM ~0V)");
      else if (pzemOk && pzV > AC_PRESENT_MIN_V)
        clearAlert("NO_AC_POWER");
    }
  }

  /* push ke dashboard + terima perintah web */
  if (now - lastTelemetry >= TELEMETRY_INTERVAL_MS) {
    lastTelemetry = now;
    pushTelemetry();
  }

  /* Telegram tiap 3 detik */
  if (now - lastTelegram >= TELEGRAM_CHECK_MS) {
    lastTelegram = now;
    cekPesanTelegram();
  }

  /* LCD tiap 1 detik */
  if (now - lastLcd >= LCD_INTERVAL_MS) {
    lastLcd = now;
    updateLCD();
  }

  /* watchdog WiFi */
  if (now - lastWifiCheck >= WIFI_WATCHDOG_MS) {
    lastWifiCheck = now;
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[WIFI] Terputus, coba sambung ulang...");
      WiFi.reconnect();
    }
  }

  delay(5);
}
