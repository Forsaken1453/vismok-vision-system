"""
simulate_esp32.py - Simulasi data ESP32 untuk dashboard.

Berguna saat:
  - Firmware belum di-upload ke board sungguhan
  - Mau lihat tampilan dashboard dengan data yang bergerak
  - Mau menguji sistem deteksi peringatan

Cara pakai:
    python simulator_esp32.py
    python simulator_esp32.py --scenario motor-macet
    python simulator_esp32.py --server http://192.168.1.3:8080

Skenario:
    normal         Semua normal (default)
    motor-macet    Motor tidak menarik arus (peak rendah)
    ac-hilang      Daya AC terputus
    sensor-putus   ZMPT101B dropout
    offline        Kirim data lalu berhenti mendadak
"""

import argparse
import json
import math
import random
import sys
import time
import urllib.request
from datetime import datetime, timedelta

SLOTS = [
    {"time": "07:00", "takar": 1.0},
    {"time": "12:00", "takar": 1.0},
    {"time": "17:00", "takar": 1.0},
]


def secs_until(hh, mm):
    now = datetime.now()
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return int((target - now).total_seconds())


def next_slot():
    best_i, best_s = -1, 999999
    for i, s in enumerate(SLOTS):
        hh, mm = map(int, s["time"].split(":"))
        d = secs_until(hh, mm)
        if d < best_s:
            best_s, best_i = d, i
    return best_i, best_s


def post(url, payload, timeout=5):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"  [x] Gagal kirim: {exc}", file=sys.stderr)
        return None


def build_frame(scenario, motor_running, motor_start, peak_i, tick):
    """Bangun satu frame telemetry.

    Mengembalikan (frame, motor_running_baru) supaya status motor
    di caller ikut ter-update.
    """
    slot_i, secs_next = next_slot()
    now = datetime.now()

    # --- AC ---
    ac_v = 220.0 + math.sin(tick / 12.0) * 2.2 + random.uniform(-1.2, 1.2)
    ac_i = 0.21 + random.uniform(-0.01, 0.01)
    power = ac_v * ac_i * 0.99
    energy = 1284.0 + tick * power / 3600.0
    freq = 50.0 + random.uniform(-0.15, 0.15)

    zmpt_v = ac_v + random.uniform(-1.5, 1.5)
    zmtp_raw = zmpt_v * 0.0106
    pzem_ok = True

    alert = {"code": "NONE", "message": "", "active": False, "since_ms": 0}

    # --- terapkan skenario ---
    if scenario == "motor-macet":
        peak_i = 0.05
    elif scenario == "ac-hilang":
        ac_v, ac_i, power, zmpt_v = 0.0, 0.0, 0.0, 0.0
        alert = {"code": "NO_AC_POWER",
                 "message": "Daya AC tidak terdeteksi (PZEM ~0V)",
                 "active": True, "since_ms": 0}
    elif scenario == "sensor-putus":
        zmpt_v = 0.4
        alert = {"code": "SENSOR_FAULT",
                 "message": "ZMPT101B baca ~0 (kemungkinan putus)",
                 "active": True, "since_ms": 0}

    # --- motor ---
    remain = 0.0
    if motor_running:
        elapsed = (time.time() - motor_start)
        remain = max(0.0, 3.0 * SLOTS[slot_i]["takar"] - elapsed)
        motor_cur = peak_i + math.sin(tick * 0.9) * 0.05
        if remain <= 0:
            motor_running = False
    else:
        motor_cur = random.uniform(0.0, 0.04)

    if motor_running and peak_i < 0.15:
        alert = {"code": "MOTOR_NO_CURRENT",
                 "message": "Motor tidak terdeteksi berputar (arus peak terlalu rendah)",
                 "active": True, "since_ms": 0}

    frame = {
        "device_id": "fish-feeder-01",
        "uptime_ms": int((time.time() - START_TIME) * 1000),
        "free_heap": 142336 + int(math.sin(tick / 20.0) * 8000),
        "rssi": -55 + int(math.sin(tick / 30.0) * 6),
        "time": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "rtc_ok": True,
        "auto_feed": True,
        "next_slot_index": slot_i,
        "secs_to_next": secs_next,
        "schedule": SLOTS,
        "motor": {
            "running": motor_running,
            "peak_current": round(peak_i, 3),
            "last_takar": SLOTS[slot_i]["takar"],
            "remaining_ms": int(remain * 1000),
        },
        "sensors": {
            "zmtp_voltage": round(zmpt_v, 1),
            "zmtp_raw": round(zmtp_raw, 4),
            "acs_baseline": round(1.651 + random.uniform(-0.004, 0.004), 4),
            "motor_current": round(motor_cur, 3),
            "peak_current": round(peak_i, 3),
            "ac_voltage": round(ac_v, 1),
            "ac_current": round(ac_i, 3),
            "power_w": round(power, 1),
            "energy_wh": round(energy, 1),
            "freq": round(freq, 1),
            "power_factor": 0.99,
            "pzem_ok": pzem_ok,
        },
        "alert": alert,
    }
    return frame, motor_running


START_TIME = time.time()


def main():
    global SLOTS

    ap = argparse.ArgumentParser(description="Simulator ESP32 untuk dashboard")
    ap.add_argument("--server", default="http://127.0.0.1:8080",
                    help="URL server dashboard (default: http://127.0.0.1:8080)")
    ap.add_argument("--scenario", default="normal",
                    choices=["normal", "motor-macet", "ac-hilang",
                             "sensor-putus", "offline"])
    ap.add_argument("--count", type=int, default=0,
                    help="Jumlah frame (0 = jalan terus)")
    args = ap.parse_args()

    url = args.server.rstrip("/") + "/api/ingest"

    print("=" * 52)
    print("  SIMULATOR ESP32")
    print("=" * 52)
    print(f"  Server  : {url}")
    print(f"  Skenario: {args.scenario}")
    print(f"  Jadwal  : {', '.join(s['time'] for s in SLOTS)}")
    print("  Ctrl+C untuk berhenti\n")

    motor_running = False
    motor_start = 0.0
    peak_i = 0.0
    tick = 0
    sent = 0
    ok_count = 0

    try:
        while args.count == 0 or sent < args.count:
            # Motor jalan 5 detik tiap 20 detik, biar terlihat di grafik
            if not motor_running and tick % 20 == 0:
                motor_running = True
                motor_start = time.time()
                peak_i = 0.05 if args.scenario == "motor-macet" else 1.24

            frame, motor_running = build_frame(
                args.scenario, motor_running, motor_start, peak_i, tick)
            res = post(url, frame)

            if res:
                ok_count += 1
                if res.get("commands"):
                    for cmd in res["commands"]:
                        print(f"  [!] Perintah diterima: {cmd}")
                        if cmd.get("type") == "FEED_NOW":
                            motor_running = True
                            motor_start = time.time()
                            peak_i = 1.24
                        elif cmd.get("type") == "SET_SCHEDULE":
                            SLOTS = cmd.get("slots", SLOTS)
                            print(f"  [!] Jadwal baru: {SLOTS}")

                if tick % 5 == 0:
                    s = frame["sensors"]
                    print(f"  [{frame['time']}]  "
                          f"{s['ac_voltage']:.0f}V  {s['power_w']:.0f}W  "
                          f"motor {s['motor_current']:.2f}A  "
                          f"motor={'JALAN' if frame['motor']['running'] else 'idle'}  "
                          f"alert={frame['alert']['code']}")

            # Skenario offline: kirim 8 frame lalu berhenti diam
            if args.scenario == "offline" and tick == 8:
                print("\n  [offline] Berhenti mengirim data...\n")
                while True:
                    time.sleep(1)

            tick += 1
            sent += 1
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"\n  Selesai. {ok_count}/{sent} frame terkirim.\n")


if __name__ == "__main__":
    main()