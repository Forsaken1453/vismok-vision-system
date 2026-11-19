"""
alerts.py - Aturan deteksi "pelempar gagal".

Firmware sudah mendeteksi sebagian masalah, tapi beberapa kondisi
hanya bisa dinilai di sisi laptop karena butuh histori (misal
"data tidak masuk selama 30 detik").

Semua aturan di sini mengembalikan daftar alert bertingkat:
  "error"  -> kondisi berbahaya, butuh tindakan
  "warn"   -> mencurigakan, perlu dicek
  "info"   -> informatif
"""

from datetime import datetime

from core.storage import safe_num

# Ambang batas
OFFLINE_AFTER_SEC = 10        # data ESP32 tidak masuk > 10 detik
MOTOR_STUCK_CURRENT = 0.15    # A, peak arus motor dianggap macet
NO_AC_VOLTAGE = 20.0          # V, di bawah ini daya AC dianggap mati
DEGRADED_WIFI_RSSI = -75      # dBm, di bawah ini WiFi sangat lemah
LOW_FREE_HEAP = 30000         # byte, RAM ESP32 menipis


def evaluate(snapshot: dict) -> list[dict]:
    """Periksa snapshot state, kembalikan daftar alert aktif."""
    alerts = []
    now = datetime.now()

    sensors = snapshot.get("sensors", {}) or {}
    motor = snapshot.get("motor", {}) or {}
    fw_alert = snapshot.get("alert", {}) or {}

    # Semua angka dibuat aman (lapis kedua, setelah coercion di storage)
    ac_v = safe_num(sensors.get("ac_voltage"))
    zmpt_v = safe_num(sensors.get("zmtp_voltage"))
    peak = safe_num(motor.get("peak_current"))
    rssi = safe_num(snapshot.get("rssi"))
    heap = safe_num(snapshot.get("free_heap"))
    since = safe_num(snapshot.get("seconds_since_data"), -1)

    # ---- 1. Laporan langsung dari firmware ----
    if fw_alert.get("active"):
        code = fw_alert.get("code", "UNKNOWN")
        alerts.append({
            "code": code,
            "message": fw_alert.get("message", ""),
            "level": "error" if code in ("MOTOR_NO_CURRENT", "NO_AC_POWER")
                     else "warn",
            "source": "firmware",
            "time": now.strftime("%H:%M:%S"),
        })

    # ---- 2. ESP32 tidak mengirim data ----
    if not snapshot.get("connected"):
        if since < 0:
            msg = "Belum pernah menerima data dari ESP32"
        else:
            msg = f"Tidak ada data dari ESP32 selama {since:.0f} detik"
        alerts.append({
            "code": "OFFLINE",
            "message": msg,
            "level": "error",
            "source": "server",
            "time": now.strftime("%H:%M:%S"),
        })

    # ---- 3. Daya AC hilang ----
    if sensors.get("pzem_ok") and ac_v < NO_AC_VOLTAGE:
        alerts.append({
            "code": "NO_AC_POWER",
            "message": f"Tegangan AC {ac_v:.0f}V - stopkontak atau kabel bermasalah",
            "level": "error",
            "source": "server",
            "time": now.strftime("%H:%M:%S"),
        })

    # ---- 4. Motor mungkin macet (berdasarkan peak run terakhir) ----
    if (snapshot.get("control_mode") not in ("telemetry_only", "capstone")
            and not motor.get("running") and 0 < peak < MOTOR_STUCK_CURRENT):
        alerts.append({
            "code": "MOTOR_LOW_CURRENT",
            "message": f"Arus motor terakhir cuma {peak:.2f}A - mungkin macet atau kering",
            "level": "warn",
            "source": "server",
            "time": now.strftime("%H:%M:%S"),
        })

    # ---- 5. Sensor ZMPT dropout ----
    if ac_v > NO_AC_VOLTAGE and zmpt_v < 5.0:
        alerts.append({
            "code": "ZMPT_DROPOUT",
            "message": f"ZMPT101B baca {zmpt_v:.1f}V padahal AC {ac_v:.0f}V - sensor putus/kabel",
            "level": "warn",
            "source": "server",
            "time": now.strftime("%H:%M:%S"),
        })

    # ---- 6. RTC tidak siap ----
    if not snapshot.get("rtc_ok"):
        alerts.append({
            "code": "RTC_NOT_READY",
            "message": "RTC DS3231 belum siap - jadwal mungkin tidak jalan",
            "level": "warn",
            "source": "server",
            "time": now.strftime("%H:%M:%S"),
        })

    # ---- 7. WiFi lemah ----
    if snapshot.get("connected") and rssi < DEGRADED_WIFI_RSSI:
        alerts.append({
            "code": "WIFI_WEAK",
            "message": f"Sinyal WiFi lemah ({rssi:.0f} dBm) - data bisa terputus",
            "level": "info",
            "source": "server",
            "time": now.strftime("%H:%M:%S"),
        })

    # ---- 8. RAM ESP32 menipis ----
    if heap and heap < LOW_FREE_HEAP:
        alerts.append({
            "code": "LOW_MEMORY",
            "message": f"RAM ESP32 tinggal {int(heap)//1024}KB - stabilkan dengan restart",
            "level": "warn",
            "source": "server",
            "time": now.strftime("%H:%M:%S"),
        })

    return alerts


def worst_level(alerts: list[dict]) -> str:
    """Level tertinggi dari daftar alert."""
    if not alerts:
        return "ok"
    order = {"ok": 0, "info": 1, "warn": 2, "error": 3}
    return max((a["level"] for a in alerts), key=lambda l: order.get(l, 0))