"""
storage.py - Penyimpanan data & status global untuk dashboard.

Tiga bagian:
  1. State   : snapshot terakhir dari ESP32 (dict)
  2. History : ring buffer in-memory (deque) untuk grafik
  3. Config  : settings.json (jadwal, nama perangkat, dll)

History sengaja hanya di RAM. Kalau app ditutup, data hilang.
Ini pilihan sadar supaya hemat storage (total project < 200 MB).
"""

import json
import os
import threading
from collections import deque
from datetime import datetime

# ------------------------------------------------------------------ path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

os.makedirs(DATA_DIR, exist_ok=True)

# Berapa titik disimpan. 720 titik x 1 detik = 12 menit
BUFFER_SIZE = 720

# Metrik yang digrafikkan
METRICS = [
    ("ac_voltage", "Tegangan AC", "V", "#38bdf8"),
    ("power_w", "Daya", "W", "#a78bfa"),
    ("motor_current", "Arus Motor", "A", "#fb923c"),
    ("secs_to_next", "Menit ke Feed", "", "#34d399"),
]

EXPORT_COLUMNS = [
    ("time", "Waktu"),
    ("ac_voltage", "Tegangan AC (V)"),
    ("ac_current", "Arus AC (A)"),
    ("power_w", "Daya (W)"),
    ("energy_wh", "Energi Kumulatif (Wh)"),
    ("zmtp_voltage", "Tegangan ZMPT101B (V)"),
    ("motor_current", "Arus Motor (A)"),
    ("wifi_rssi", "Sinyal WiFi (dBm)"),
    ("feed_count_today", "Pakan Hari Ini (kali)"),
    ("tariff_rp_per_kwh", "Tarif (Rp/kWh)"),
    ("today_kwh", "Konsumsi Hari Ini (kWh)"),
    ("today_cost_rp", "Biaya Hari Ini (Rp)"),
    ("month_kwh", "Konsumsi Bulan Ini (kWh)"),
    ("month_cost_rp", "Biaya Bulan Ini (Rp)"),
    ("projected_month_cost_rp", "Proyeksi Tagihan Bulan Ini (Rp)"),
    ("rtc_ok", "RTC Siap"),
    ("motor_running", "Motor Berjalan"),
    ("auto_feed", "Mode Otomatis"),
    ("free_heap", "Heap ESP32 (byte)"),
    ("alert_code", "Kode Peringatan"),
    ("alert_message", "Pesan Peringatan"),
]

_lock = threading.RLock()


def safe_num(value, default: float = 0.0) -> float:
    """Ubah apa pun jadi float. Menangkis input rusak dari ESP32
    supaya dashboard tidak ikut crash."""
    if value is None or isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default: int = 0) -> int:
    return int(safe_num(value, default))


# Field yang HARUS berupa angka. Kalau ESP32 mengirim string atau null,
# dik coerced di sini supaya tidak bikin error di tempat lain.
NUMERIC_FIELDS = {
    "uptime_ms", "free_heap", "rssi", "secs_to_next", "next_slot_index",
    "zmtp_voltage", "zmtp_raw", "acs_baseline", "motor_current",
    "peak_current", "ac_voltage", "ac_current", "power_w", "energy_wh",
    "freq", "power_factor", "remaining_ms", "last_takar", "since_ms",
    "feed_count_today",
}


# ================================================================ STATE
class State:
    """Snapshot terakhir yang dikirim ESP32."""

    def __init__(self):
        self.last = {
            "device_id": "fish-feeder-01",
            "connected": False,
            "uptime_ms": 0,
            "free_heap": 0,
            "rssi": 0,
            "control_mode": "command",
            "feed_count_today": 0,
            "time": "",
            "rtc_ok": False,
            "auto_feed": True,
            "next_slot_index": -1,
            "secs_to_next": 0,
            "schedule": [],
            "motor": {
                "running": False,
                "state_known": True,
                "peak_current": 0.0,
                "last_takar": 0.0,
                "remaining_ms": 0,
            },
            "sensors": {
                "zmtp_voltage": 0.0,
                "zmtp_raw": 0.0,
                "acs_baseline": 0.0,
                "motor_current": 0.0,
                "peak_current": 0.0,
                "ac_voltage": 0.0,
                "ac_current": 0.0,
                "power_w": 0.0,
                "energy_wh": 0.0,
                "freq": 0.0,
                "power_factor": 0.0,
                "pzem_ok": False,
            },
            "alert": {"code": "NONE", "message": "", "active": False, "since_ms": 0},
        }
        self.last_seen = None  # datetime saat data terakhir masuk

    def update(self, payload: dict):
        """Gabungkan payload baru ke state.

        Field numerik dipaksa jadi angka supaya data rusak dari ESP32
        tidak menyebabkan dashboard error.
        """
        if not isinstance(payload, dict):
            return

        with _lock:
            for key, value in payload.items():
                # merge sederhana 1 tingkat
                if key in self.last and isinstance(self.last[key], dict) \
                        and isinstance(value, dict):
                    for sub_key, sub_val in value.items():
                        if sub_key in NUMERIC_FIELDS:
                            self.last[key][sub_key] = safe_num(sub_val)
                        else:
                            self.last[key][sub_key] = sub_val
                elif key in NUMERIC_FIELDS:
                    self.last[key] = safe_num(value)
                elif key in ("connected",):
                    # dihitung sendiri di snapshot()
                    continue
                else:
                    self.last[key] = value
            self.last_seen = datetime.now()

    def snapshot(self) -> dict:
        with _lock:
            data = dict(self.last)
            # hitung status koneksi
            if self.last_seen:
                age = (datetime.now() - self.last_seen).total_seconds()
                data["connected"] = age < 10
                data["seconds_since_data"] = round(age, 1)
            else:
                data["connected"] = False
                data["seconds_since_data"] = None
            return data


state = State()


# ============================================================== HISTORY
class History:
    """Ring buffer per metrik. capped, tidak pernah tumbuh."""

    def __init__(self, size: int = BUFFER_SIZE):
        self.size = size
        self.buffers = {key: deque(maxlen=size) for key, *_ in METRICS}
        self.timestamps = deque(maxlen=size)
        self.records = deque(maxlen=size)

    def append(self, sensors: dict, secs_to_next: int, snapshot: dict = None):
        snapshot = snapshot or {}
        motor = snapshot.get("motor", {}) or {}
        alert = snapshot.get("alert", {}) or {}
        now = datetime.now()
        with _lock:
            self.timestamps.append(now.strftime("%H:%M:%S"))
            for key, *_ in METRICS:
                self.buffers[key].append(float(sensors.get(key, 0) or 0))
            billing = snapshot.get("billing", {}) or {}
            self.records.append({
                "time": snapshot.get("time") or now.isoformat(timespec="seconds"),
                "ac_voltage": sensors.get("ac_voltage"),
                "ac_current": sensors.get("ac_current"),
                "power_w": sensors.get("power_w"),
                "energy_wh": sensors.get("energy_wh"),
                "zmtp_voltage": sensors.get("zmtp_voltage"),
                "motor_current": sensors.get("motor_current"),
                "wifi_rssi": snapshot.get("rssi"),
                "feed_count_today": snapshot.get("feed_count_today"),
                "tariff_rp_per_kwh": billing.get("tariff_rp_per_kwh"),
                "today_kwh": billing.get("today_kwh"),
                "today_cost_rp": billing.get("today_cost_rp"),
                "month_kwh": billing.get("month_kwh"),
                "month_cost_rp": billing.get("month_cost_rp"),
                "projected_month_cost_rp": billing.get("projected_month_cost_rp"),
                "rtc_ok": snapshot.get("rtc_ok"),
                "motor_running": motor.get("running")
                    if motor.get("state_known", True) else None,
                "auto_feed": snapshot.get("auto_feed"),
                "free_heap": snapshot.get("free_heap"),
                "alert_code": alert.get("code"),
                "alert_message": alert.get("message"),
            })

    def series(self, count: int = 300) -> dict:
        """Kembalikan N titik terakhir per metrik."""
        with _lock:
            n = min(count, self.size)
            return {
                "labels": list(self.timestamps)[-n:],
                "series": {key: list(buf)[-n:] for key, buf in self.buffers.items()},
                "meta": {key: {"label": lab, "unit": unit, "color": color}
                         for key, lab, unit, color in METRICS},
            }

    def clear(self):
        with _lock:
            for buf in self.buffers.values():
                buf.clear()
            self.timestamps.clear()
            self.records.clear()

    def export_records(self) -> list[dict]:
        with _lock:
            return [dict(record) for record in self.records]


history = History()


# =============================================================== CONFIG
DEFAULT_SETTINGS = {
    "device_id": "fish-feeder-01",
    "auto_feed": True,
    "base_second": 3.0,
    "schedule": [
        {"time": "07:00", "takar": 1.0},
        {"time": "12:00", "takar": 1.0},
        {"time": "17:00", "takar": 1.0},
    ],
    "history_points": 300,
    "tariff_rp_per_kwh": 1444.70,
}


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            merged = dict(DEFAULT_SETTINGS)
            merged.update(saved)
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    save_settings(DEFAULT_SETTINGS)
    return dict(DEFAULT_SETTINGS)


def save_settings(data: dict) -> dict:
    with _lock:
        current = load_settings_raw()
        current.update(data)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        return current


def load_settings_raw() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_SETTINGS)


settings = load_settings()


# ============================================================= COMMANDS
class CommandQueue:
    """Perintah dari browser menunggu di sini, diambil ESP32 saat
    dia POST /api/ingest berikutnya (1 detik kemudian)."""

    def __init__(self):
        self._queue: list[dict] = []

    def push(self, cmd_type: str, **kwargs):
        with _lock:
            self._queue.append({"type": cmd_type, **kwargs})
        print(f"[CMD] Ditambahkan: {cmd_type} {kwargs}")

    def drain(self) -> list[dict]:
        """Ambil dan kosongkan antrean. Dipanggil sekali per ingest."""
        with _lock:
            items = self._queue[:]
            self._queue.clear()
            return items

    def peek_count(self) -> int:
        with _lock:
            return len(self._queue)


commands = CommandQueue()


# =============================================================== ALERT
class AlertLog:
    """Riwayat alert di sesi ini (RAM). Maks 50 entri."""

    def __init__(self, limit: int = 50):
        self.limit = limit
        self.items: list[dict] = []
        self._current = None

    def record(self, alert: dict, at: datetime):
        with _lock:
            code = alert.get("code", "NONE")
            active = bool(alert.get("active"))

            if active and (self._current != code):
                self.items.append({
                    "time": at.strftime("%H:%M:%S"),
                    "code": code,
                    "message": alert.get("message", ""),
                    "status": "active",
                })
                self._current = code
            elif (not active) and self._current == code:
                self.items.append({
                    "time": at.strftime("%H:%M:%S"),
                    "code": code,
                    "message": alert.get("message", ""),
                    "status": "resolved",
                })
                self._current = None

            if len(self.items) > self.limit:
                self.items = self.items[-self.limit:]

    def recent(self, count: int = 20) -> list[dict]:
        with _lock:
            return self.items[-count:][::-1]


alert_log = AlertLog()