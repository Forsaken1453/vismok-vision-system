/* =====================================================================
 *  fish_feeder.ino
 *  Firmware Pelempar Pakan Ikan Otomatis
 *  ---------------------------------------------------------------------
 *  - Baca ZMPT101B  : tegangan AC
 *  - Baca ACS712    : arus DC motor
 *  - Baca PZEM004T-V4 : voltase/arus/daya/energi AC (UART2)
 *  - Motor RS555 12V via driver, durasi = 3 detik x takaran
 *  - RTC DS3231 untuk jadwal 07:00 / 12:00 / 17:00
 *  - Kirim telemetry ke laptop (Flask) setiap 1 detik
 *  - Peringatan otomatis bila pelempar gagal
 *
 *  Wiring lengkap: docs/WIRING.md
 * ===================================================================== */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <RTClib.h>
#include <ArduinoJson.h>
#include <math.h>

#include "config.h"

/* =========================== STATE =========================== */

/* Sensor */
float  zmtpVoltage    = 0.0f;      // tegangan AC hasil kalibrasi (volt)
float  acsCurrent     = 0.0f;      // arus motor (ampere, signed)
float  acsBaseline    = 0.0f;      // baseline ADC saat motor mati
float  acsPeak        = 0.0f;      // peak arus saat motor terakhir
float  zmtpRaw        = 0.0f;
float  zmtpScale      = 1.0f;

/* PZEM */
float  pzV = 0, pzI = 0, pzP = 0, pzWh = 0, pzHz = 0, pzPF = 0;
bool   pzemOk = false;

/* Motor */
bool     motorRunning   = false;
uint32_t motorStartMs   = 0;
uint32_t motorDurationMs= 0;
float    motorPeakI     = 0.0f;
float    motorLastTakar = 0.0f;
uint32_t motorSettleMs  = 0;   // tunda sebelum ukur peak (motor start up)

/* Jadwal */
struct Slot { uint8_t hh, mm; float takar; bool valid; };
Slot slots[3] = {
  { 7,  0, DEFAULT_TAKAR, true },
  {12,  0, DEFAULT_TAKAR, true },
  {17,  0, DEFAULT_TAKAR, true }
};
bool     autoFeedEnabled = true;
bool     slotDone[3]     = { false, false, false };
DateTime rtcNow;
bool     rtcOk = false;
int      nextSlotIdx = -1;
uint32_t secsToNext = 0;

/* Alert */
enum AlertCode {
  AL_NONE = 0, AL_NO_AC, AL_MOTOR_NO_CURRENT, AL_SCHEDULE_MISSED,
  AL_SENSOR_FAULT, AL_RTC_LOST, AL_OFFLINE
};
String  alertCode    = "NONE";
String  alertMessage = "";
uint32_t alertSince  = 0;

/* Koneksi & timing */
unsigned long lastTelemetry = 0;
unsigned long lastPzem      = 0;
unsigned long lastBtn       = 0;
unsigned long btnDownSince  = 0;
bool          serverReachable = false;

/* ======================= HELPER WAKTU ======================= */

int epochLocal() {
  if (!rtcOk) return (int)(millis() / 1000);
  time_t t = rtcNow.unixtime();
  return (int)t;
}

int secsUntil(uint8_t hh, uint8_t mm) {
  int nowS = epochLocal();
  int target = (hh * 3600) + (mm * 60);
  int nowd   = nowS % 86400;
  int d = target - nowd;
  if (d <= 0) d += 86400;
  return d;
}

void findNextSlot() {
  int best = -1, bestD = 999999;
  for (int i = 0; i < 3; i++) {
    if (!slots[i].valid) continue;
    int d = secsUntil(slots[i].hh, slots[i].mm);
    if (d < bestD) { bestD = d; best = i; }
  }
  nextSlotIdx  = best;
  secsToNext   = (best >= 0) ? bestD : 0;
}

void raiseAlert(const char* code, const char* msg) {
  if (alertCode == code) return;         // sudah aktif, tidak spam
  alertCode    = code;
  alertMessage = msg;
  alertSince   = millis();
  Serial.printf("[ALERT] %s - %s\n", code, msg);
}
void clearAlert() {
  alertCode = "NONE"; alertMessage = ""; alertSince = 0;
}

/* ============================ RTC ============================ */

bool setupRTC() {
  Wire.begin(PIN_SDA, PIN_SCL);
  if (!rtc.begin()) { Serial.println("[RTC] DS3231 tidak ditemukan"); return false; }

  if (rtc.lostPower()) {
    Serial.println("[RTC] Baterai habis, set ke waktu kompilasi");
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }
  // Sinkronkan ke NTP bila ada internet, selaraskan yang tidak ada
  if (WiFi.status() == WL_CONNECTED) {
    configTime(7 * 3600, 0, "id.pool.ntp.org", "pool.ntp.org");
    struct tm t;
    if (getLocalTime(&t, 2000)) {
      rtc.adjust(DateTime(t.tm_year + 1900, t.tm_mon + 1, t.tm_mday,
                         t.tm_hour, t.tm_min, t.tm_sec));
      Serial.println("[RTC] Disinkronkan dari NTP (WIB)");
    }
  }
  rtcNow = rtc.now();
  rtcOk  = true;
  Serial.print("[RTC] Waktu: ");
  Serial.println(rtcNow.formatISO8601());
  return true;
}

/* ========================== SENSOR =========================== */

void setupAnalog() {
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);   // range ~0-3.3V penuh
}

/* Kalibrasi ZMPT101B terhadap PZEM004T yang terisolasi optocoupler.
 * MontrelItem kan ZMPT mengikuti proporsional dengan tegangan AC,
 * sehingga cukup 1 titik acuan. */
void calibrateZMPT() {
#if ZMPT_AUTO_CALIBRATE
  if (!pzemOk || pzV < AC_PRESENT_MIN_V) return;
  float rawSum = 0;
  int n = 0;
  for (int i = 0; i < ZMPT_CAL_SAMPLES; i++) {
    rawSum += analogRead(PIN_ZMPT101B) * (3.3f / 4095.0f);
    delay(50); n++;
  }
  float rawAvg = rawSum / n;
  zmtpScale = pzV / rawAvg;
  zmtpVoltage = pzV;
  Serial.printf("[CAL] ZMPT raw=%.3fV acuan=%.1fV scale=%.5f\n",
                rawAvg, pzV, zmtpScale);
#else
  zmtpScale = ZMPT_CAL_MANUAL;
#endif
}

void readSensors() {
  /* ---- ZMPT101B ---- */
  int raw = analogRead(PIN_ZMPT101B);
  zmtpRaw = raw * (3.3f / 4095.0f);
  zmtpVoltage = zmtpRaw * zmtpScale;
  // ZMPT biasanya noisy; rata-rata bergerak sederhana
  static float zFilt = 0;
  zFilt = (zFilt == 0) ? zmtpVoltage : (zFilt * 0.8f + zmtpVoltage * 0.2f);
  zmtpVoltage = zFilt;

  /* ---- ACS712 ---- */
  int  aRaw = analogRead(PIN_ACS712);
  float aV   = aRaw * (3.3f / 4095.0f);
  float amps = (aV - (3.3f * 0.5f)) / ACS_SENSITIVITY;

  if (!motorRunning) {
    // Kalibrasi baseline saat motor diam (idle ~ VCC/2)
    static float base = 0;
    base = (base == 0) ? aV : (base * ACS_FILTER_ALPHA + aV * (1 - ACS_FILTER_ALPHA));
    acsBaseline = base;
    acsCurrent  = (aV - base) / ACS_SENSITIVITY;
    if (acsCurrent < 0) acsCurrent = -acsCurrent;
  } else {
    acsCurrent = amps;
    if (abs(amps) > acsPeak) acsPeak = abs(amps);
  }
}

/* PZEM004T-V4 parser (Modbus RTU gaya custom ASCII). */
void readPzem() {
  uint8_t cmd[4] = {0xF8, 0x00, 0x64, 0x01};   // read input register 0x0000, 2 register
  Serial2.write(cmd[0]); Serial2.flush();
  delay(50);
  Serial2.write(cmd[1]); Serial2.flush();
  delay(50);
  Serial2.write(cmd[2]); Serial2.flush();
  delay(50);
  Serial2.write(cmd[3]); Serial2.flush();
  delay(200);

  uint8_t buf[35];
  int idx = 0;
  unsigned long t0 = millis();
  while (Serial2.available() && idx < 35 && millis() - t0 < 500) {
    buf[idx++] = Serial2.read();
    delay(10);
  }
  if (idx < 25) { pzemOk = false; return; }
  if (buf[0] != 0xF8 || buf[1] != 0x00) { pzemOk = false; return; }

  // [0]=F8 [1]=00, lalu 6 pasang byte
  pzV  = ((buf[3]  << 8) | buf[2])  * 0.1f;
  pzI  = ((buf[7]  << 8) | buf[6])  * 0.001f;
  pzP  = ((buf[11] << 8) | buf[10]) * 0.1f;
  pzWh = ((buf[15] << 8) | buf[14]) * 0.1f;
  pzHz = ((buf[17] << 8) | buf[16]) * 0.1f;
  pzPF = ((buf[19] << 8) | buf[18]) * 0.001f;
  pzemOk = true;
}

/* ========================== MOTOR ============================ */

void setMotor(bool on) {
  digitalWrite(PIN_MOTOR_EN, on ? LOW : HIGH);  // active LOW
  if (!on) {
    digitalWrite(PIN_MOTOR_PWM, 0);
    digitalWrite(PIN_MOTOR_DIR, HIGH);
    ledcWrite(PIN_MOTOR_PWM, 0);
  }
}

void startMotor(float takar) {
  if (motorRunning) return;
  takar = constrain(takar, MIN_TAKAR, MAX_TAKAR);
  motorRunning    = true;
  motorStartMs    = millis();
  motorDurationMs = (uint32_t)(MOTOR_BASE_SECOND * 1000.0f * takar);
  motorPeakI      = 0.0f;
  motorLastTakar  = takar;
  motorSettleMs   = motorStartMs + 200;   // abaikan 200ms start-up

  digitalWrite(PIN_MOTOR_DIR, HIGH);
  ledcSetup(PIN_MOTOR_PWM, 1000, 8);
  ledcAttachPin(PIN_MOTOR_PWM, 1000);
  digitalWrite(PIN_MOTOR_EN, LOW);
  ledcWrite(PIN_MOTOR_PWM, MOTOR_PWM_SOFT);

  Serial.printf("[MOTOR] Start %.2f takar = %lu ms\n", takar, motorDurationMs);
}

void updateMotor() {
  if (!motorRunning) return;
  if (millis() - motorStartMs >= motorDurationMs) {
    stopMotor();
  }
}

void stopMotor() {
  ledcWrite(PIN_MOTOR_PWM, 0);
  ledcDetachPin(PIN_MOTOR_PWM);
  digitalWrite(PIN_MOTOR_EN, HIGH);
  digitalWrite(PIN_MOTOR_DIR, HIGH);
  motorRunning = false;

  // Evaluasi hasil: peak arus cukup = motor benar-benar berputar
  if (motorPeakI < MOTOR_MIN_PEAK_CURRENT) {
    raiseAlert("MOTOR_NO_CURRENT",
      "Motor tidak terdeteksi berputar (arus peak terlalu rendah)");
    Serial.printf("[MOTOR] Selesai. Peak=%.3fA -> GAGAL\n", motorPeakI);
  } else {
    if (alertCode == "MOTOR_NO_CURRENT") clearAlert();
    Serial.printf("[MOTOR] Selesai. Peak=%.3fA -> OK\n", motorPeakI);
  }
}

/* ======================== SCHEDULER ========================== */

void resetSlotDone() {
  for (int i = 0; i < 3; i++) slotDone[i] = false;
}

void updateSchedule() {
  if (!rtcOk) return;
  uint8_t hh = rtcNow.hour(), mm = rtcNow.minute();

  for (int i = 0; i < 3; i++) {
    if (!slots[i].valid) { slotDone[i] = true; continue; }
    // Lewati slot yang sudah dilewati menit ini tapi belum > grace
    if (slotDone[i]) continue;

    // Sudah lewat jadwal?
    if (hh > slots[i].hh || (hh == slots[i].hh && mm >= slots[i].mm)) {
      if (!motorRunning) {
        Serial.printf("[SCHED] Trigger slot %d %02d:%02d\n", i, slots[i].hh, slots[i].mm);
        slotDone[i] = true;
        startMotor(slots[i].takar);
      }
    }
  }

  // Deteksi jadwal terlewat (skip karena restart / RTC salah)
  if (autoFeedEnabled) {
    for (int i = 0; i < 3; i++) {
      if (!slots[i].valid || slotDone[i]) continue;
      int due = secsUntil(slots[i].hh, slots[i].mm);
      if (due > 86400 - SCHEDULE_MISS_GRACE) {
        // baru saja terlewat > grace tanpa trigger
        slotDone[i] = true;
        raiseAlert("SCHEDULE_MISSED",
          "Jadwal terlewat,-feed diskip");
        Serial.printf("[SCHED] MISSED slot %d\n", i);
      }
    }
  }

  // Reset harian saat lewat midnight
  if (hh == 0 && mm == 0) resetSlotDone();

  findNextSlot();
}

/* ======================= HTTP PUSH =========================== */

void pushTelemetry() {
  if (WiFi.status() != WL_CONNECTED) { serverReachable = false; return; }

  JsonDocument doc;
  doc["device_id"]  = "fish-feeder-01";
  doc["uptime_ms"]  = millis();
  doc["free_heap"]  = ESP.getFreeHeap();
  doc["rssi"]       = WiFi.RSSI();

  // waktu
  if (rtcOk) {
    DateTime t = rtc.now();
    char ts[24]; strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%S", &t);
    doc["time"]   = String(ts);
    doc["rtc_ok"] = true;
  } else {
    doc["time"]   = "";
    doc["rtc_ok"] = false;
  }

  // jadwal
  doc["auto_feed"]      = autoFeedEnabled;
  doc["next_slot_index"] = nextSlotIdx;
  doc["secs_to_next"]   = secsToNext;

  JsonArray sj = doc.createNestedArray("schedule");
  for (int i = 0; i < 3; i++) {
    char hhmm[8];
    snprintf(hhmm, sizeof(hhmm), "%02d:%02d", slots[i].hh, slots[i].mm);
    JsonObject o = sj.createNestedObject();
    o["time"]  = String(hhmm);
    o["takar"] = slots[i].takar;
  }

  // motor
  JsonObject mo = doc.createNestedObject("motor");
  mo["running"]      = motorRunning;
  mo["peak_current"] = motorPeakI;
  mo["last_takar"]   = motorLastTakar;
  mo["remaining_ms"] = motorRunning ? (motorDurationMs - (millis() - motorStartMs)) : 0;

  // sensor
  JsonObject s = doc.createNestedObject("sensors");
  s["zmtp_voltage"]  = roundf(zmtpVoltage * 10) / 10;
  s["zmtp_raw"]      = roundf(zmtpRaw * 1000) / 1000;
  s["acs_baseline"]  = roundf(acsBaseline * 1000) / 1000;
  s["motor_current"] = roundf(acsCurrent * 1000) / 1000;
  s["peak_current"]  = roundf(motorPeakI * 1000) / 1000;
  s["ac_voltage"]    = pzemOk ? roundf(pzV * 10) / 10 : 0;
  s["ac_current"]    = pzemOk ? roundf(pzI * 1000) / 1000 : 0;
  s["power_w"]       = pzemOk ? roundf(pzP * 10) / 10 : 0;
  s["energy_wh"]     = pzemOk ? roundf(pzWh * 10) / 10 : 0;
  s["freq"]          = pzemOk ? roundf(pzHz * 10) / 10 : 0;
  s["power_factor"]  = pzemOk ? roundf(pzPF * 1000) / 1000 : 0;
  s["pzem_ok"]       = pzemOk;

  // alert
  JsonObject a = doc.createNestedObject("alert");
  a["code"]    = alertCode;
  a["message"] = alertMessage;
  a["active"]  = (alertCode != "NONE");
  a["since_ms"] = alertSince;

  String body;
  serializeJson(doc, body);

  HTTPClient http;
  String url = String("http://") + SERVER_HOST + ":" + SERVER_PORT + "/api/ingest";
  if (!http.begin(url)) { serverReachable = false; return; }
  http.setTimeout(HTTP_PUSH_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);

  if (code == 200) { serverReachable = true; clearAlertIfServerOK(); }
  else { serverReachable = false; }

  http.end();
}

void clearAlertIfServerOK() {
  // AL_OFFLINE dicoret begitu server kembali terjangkau
  if (alertCode == "AL_OFFLINE") clearAlert();
}

/* ========================== WIFI ============================= */

void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WIFI] Menghubungkan ke ");
  Serial.print(WIFI_SSID);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < WIFI_TIMEOUT_MS) {
    delay(250);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("\n[WIFI] OK, IP = ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WIFI] GAGAL. Cek SSID/password di config.h");
  }
}

/* ========================= TOMBOL ============================ */

void updateButton() {
  int st = digitalRead(PIN_BTN_MANUAL);
  unsigned long now = millis();
  if (st == LOW) {
    if (btnDownSince == 0) btnDownSince = now;
    if (now - btnDownSince >= BTN_DEBOUNCE_MS && now - lastBtn > 3000) {
      lastBtn = now; btnDownSince = 0;
      if (!motorRunning) { Serial.println("[BTN] Feed manual"); startMotor(1.0f); }
    }
  } else {
    btnDownSince = 0;
  }
}

/* ========================== SETUP ============================ */

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(300);
  Serial.println("\n==================================");
  Serial.println(" Firmware Pelempar Pakan Ikan");
  Serial.println("==================================");

  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_MOTOR_PWM, OUTPUT);
  pinMode(PIN_MOTOR_DIR, OUTPUT);
  pinMode(PIN_MOTOR_EN, OUTPUT);
  setMotor(false);
  pinMode(PIN_BTN_MANUAL, INPUT_PULLUP);

  setupAnalog();
  setupWiFi();
  setupRTC();

  Serial2.begin(PZEM_BAUD, SERIAL_8N1, PIN_PZEM_RX, PIN_PZEM_TX);

  readPzem();
  calibrateZMPT();

  findNextSlot();
  resetSlotDone();
  Serial.println("[BOOT] Siap. Jadwal: 07:00 / 12:00 / 17:00");
}

/* ========================== LOOP ============================= */

void loop() {
  if (rtcOk) rtcNow = rtc.now();

  // 1. Jadwal
  updateSchedule();

  // 2. Motor (timer non-blocking)
  updateMotor();

  // 3. Tombol manual
  updateButton();

  // 4. Sensor
  readSensors();

  // 5. PZEM (lebih lambat, 1 detik)
  if (millis() - lastPzem >= PZEM_POLL_MS) {
    lastPzem = millis();
    readPzem();
    // Deteksi AC mati
    if (pzemOk && pzV < AC_PRESENT_MIN_V)
      raiseAlert("NO_AC_POWER", "Daya AC tidak terdeteksi (PZEM ~0V)");
    else if (pzemOk && alertCode == "NO_AC_POWER")
      clearAlert();
    // Deteksi sensor ZMTP dropout
    if (pzemOk && pzV > AC_PRESENT_MIN_V && zmtpVoltage < ZMPT_OUTLIER_MIN_V)
      raiseAlert("SENSOR_FAULT", "ZMPT101B baca ~0 (kemungkinan Putus)");
  }

  // 6. LED heartbeat
  digitalWrite(PIN_LED, serverReachable ? HIGH : LOW);

  // 7. Push telemetry
  if (millis() - lastTelemetry >= TELEMETRY_INTERVAL_MS) {
    lastTelemetry = millis();
    pushTelemetry();
  }

  delay(20);   // napas loop,_sensor & WiFi tetap responsif
}