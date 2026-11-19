"""
server.py - Server dashboard Pelempar Pakan Ikan.

Peran:
  - Menerima telemetry dari ESP32 (POST /api/ingest)
  - Menyimpan snapshot + history di RAM
  - Menyajikan dashboard web ke browser HP/laptop
  - Menerima perintah dari browser, meneruskannya ke ESP32

Cara pakai:
    python server.py
    Lalu buka http://192.168.1.3:8080 di browser
"""

import sys
import os
import socket
import threading
import time
import math
import io
import re
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

from flask import Flask, jsonify, request, send_file, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.storage import (  # noqa: E402
    state, history, settings, commands, alert_log,
    save_settings, DEFAULT_SETTINGS, METRICS, safe_num,
    EXPORT_COLUMNS,
)
from core.billing import BillingTracker  # noqa: E402
from core.alerts import evaluate, worst_level  # noqa: E402

app = Flask(__name__, static_folder=None)
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

"""Windows kadang salah menebak MIME untuk .woff2; browser butuh ini benar
supaya @font-face berhasil dimuat."""
import mimetypes  # noqa: E402
mimetypes.add_type("font/woff2", ".woff2")

PORT = 8080
EXCEL_EXPORT_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "VISMOK", "exports")
BILLING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "billing.json")
billing_tracker = BillingTracker(BILLING_FILE)
DEFAULT_SCHEDULE = [
    {"time": "07:00", "takar": 1.0},
    {"time": "12:00", "takar": 1.0},
    {"time": "17:00", "takar": 1.0},
]


# ==================================================== HALAMAN STATIS
@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(WEB_DIR, filename)


# ======================================================= TERIMA DATA
@app.route("/api/ingest", methods=["POST"])
def api_ingest():
    """ESP32 mengirim data setiap 1 detik.

    Balasan berisi perintah yang menunggu di antrean, jadi browser
    bisa mengirim perintah tanpa perlu koneksi balik ke ESP32.
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 400

    if not isinstance(payload, dict) or not payload:
        return jsonify({
            "ok": False,
            "error": "payload harus berupa objek JSON",
        }), 400

    now = datetime.now()

    if "sensors" not in payload and any(
        key in payload for key in ("voltage", "current", "power", "energy")
    ):
        def finite_value(key, default=0.0):
            value = payload.get(key)
            if value is None:
                return default
            try:
                number = float(value)
            except (TypeError, ValueError):
                return default
            return number if math.isfinite(number) else default

        clock = str(payload.get("time") or "")
        try:
            parsed_clock = datetime.strptime(clock, "%H:%M:%S")
            valid_clock = True
        except ValueError:
            try:
                parsed_clock = datetime.fromisoformat(clock)
                valid_clock = True
            except ValueError:
                valid_clock = False

        schedule = payload.get("schedule") or settings.get(
            "schedule", DEFAULT_SCHEDULE
        )
        next_slot_index = -1
        secs_to_next = 0
        if valid_clock:
            now_seconds = (
                parsed_clock.hour * 3600
                + parsed_clock.minute * 60
                + parsed_clock.second
            )
            upcoming = []
            for index, slot in enumerate(schedule):
                slot_hour, slot_minute = map(int, slot["time"].split(":"))
                delta = slot_hour * 3600 + slot_minute * 60 - now_seconds
                if delta <= 0:
                    delta += 24 * 3600
                upcoming.append((delta, index))
            if upcoming:
                secs_to_next, next_slot_index = min(upcoming)

        voltage_value = finite_value("voltage", float("nan"))
        energy_value = finite_value("energy", float("nan"))
        pzem_ok = math.isfinite(voltage_value) and math.isfinite(energy_value)
        acs_current = finite_value("acs_current")
        dashboard_control = bool(payload.get("dashboard_control", False))
        sensors = {
            "ac_voltage": voltage_value if math.isfinite(voltage_value) else 0.0,
            "ac_current": finite_value("current"),
            "power_w": finite_value("power"),
            "energy_wh": energy_value * 1000.0 if math.isfinite(energy_value) else 0.0,
            "motor_current": acs_current,
            "peak_current": 0.0,
            "zmtp_voltage": finite_value("zmpt_voltage"),
            "zmtp_raw": 0.0,
            "acs_baseline": 0.0,
            "freq": 0.0,
            "power_factor": 0.0,
            "pzem_ok": pzem_ok,
        }
        state.update({
            "device_id": payload.get("device_id", "fish-feeder-01"),
            "control_mode": "vismok" if dashboard_control else "telemetry_only",
            "uptime_ms": finite_value("uptime_ms"),
            "free_heap": finite_value("free_heap"),
            "rssi": finite_value("wifi_rssi"),
            "feed_count_today": finite_value("feed_count_today"),
            "time": clock,
            "rtc_ok": bool(payload.get("rtc_ok", valid_clock)),
            "auto_feed": bool(payload.get("auto_feed", True)),
            "schedule": schedule,
            "next_slot_index": next_slot_index,
            "secs_to_next": secs_to_next,
            "motor": {
                "running": bool(payload.get("motor_running", False)),
                "state_known": dashboard_control,
                "peak_current": 0.0,
                "last_takar": 0.0,
                "remaining_ms": 0,
            },
            "sensors": sensors,
        })
    else:
        if "control_mode" not in payload:
            payload = dict(payload)
            payload["control_mode"] = "command"
        state.update(payload)

    snapshot = state.snapshot()
    sensors = snapshot.get("sensors", {}) or {}
    if sensors.get("pzem_ok", True):
        billing = billing_tracker.update(
            safe_num(sensors.get("energy_wh")) / 1000.0,
            settings.get("tariff_rp_per_kwh", 1444.70),
            now,
        )
    else:
        billing = billing_tracker.summary(
            settings.get("tariff_rp_per_kwh", 1444.70),
            now,
        )
    state.update({"billing": billing})

    # 2. Masukkan ke history
    snap = state.last
    history.append(
        snap.get("sensors", {}) or {},
        snap.get("secs_to_next", 0) or 0,
        snap,
    )

    # 3. Catat alert dari firmware
    alert_log.record(snap.get("alert", {}) or {}, now)

    # 4. Kirim perintah yang tertunda (jika ada)
    pending = commands.drain()

    # Catatan: pakai snapshot yang sudah dibersihkan (bukan payload mentah)
    # supaya log tidak error kalau ESP32 mengirim angka sebagai string.
    snap_sensors = state.last.get("sensors", {}) or {}
    print(f"[INGEST] {state.last.get('time') or '?'}  "
          f"AC={safe_num(snap_sensors.get('ac_voltage')):.0f}V  "
          f"cmd={len(pending)}")

    return jsonify({
        "ok": True,
        "commands": pending,
        "server_time": now.isoformat(timespec="seconds"),
    })


@app.route("/api/telemetry", methods=["POST"])
def api_telemetry():
    """Terima format datar dari firmware VISMOK berbasis Telegram."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "payload harus berupa objek JSON"}), 400

    required = ("voltage", "current", "power", "energy")
    if any(key not in payload for key in required):
        return jsonify({
            "ok": False,
            "error": "field wajib: voltage, current, power, energy",
        }), 400

    def finite_value(key, default=0.0):
        value = payload.get(key)
        if value is None:
            return default
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    clock = str(payload.get("time") or "")
    try:
        datetime.strptime(clock, "%H:%M:%S")
        rtc_ok = True
    except ValueError:
        rtc_ok = False

    next_slot_index = -1
    secs_to_next = 0
    if rtc_ok:
        now_seconds = sum(int(part) * factor for part, factor in zip(
            clock.split(":"), (3600, 60, 1)
        ))
        upcoming = []
        for index, slot in enumerate(DEFAULT_SCHEDULE):
            hour, minute = map(int, slot["time"].split(":"))
            delta = hour * 3600 + minute * 60 - now_seconds
            if delta <= 0:
                delta += 24 * 3600
            upcoming.append((delta, index))
        secs_to_next, next_slot_index = min(upcoming)

    voltage_value = finite_value("voltage", float("nan"))
    energy_value = finite_value("energy", float("nan"))
    pzem_ok = math.isfinite(voltage_value) and math.isfinite(energy_value)
    acs_current = finite_value("acs_current")
    sensors = {
        "ac_voltage": voltage_value if math.isfinite(voltage_value) else 0.0,
        "ac_current": finite_value("current"),
        "power_w": finite_value("power"),
        # PZEM energy() uses kWh; the dashboard displays Wh.
        "energy_wh": energy_value * 1000.0 if math.isfinite(energy_value) else 0.0,
        "motor_current": acs_current,
        "peak_current": acs_current,
        # Keep the existing dashboard key spelling for compatibility.
        "zmtp_voltage": finite_value("zmpt_voltage"),
        "zmtp_raw": 0.0,
        "acs_baseline": 0.0,
        "freq": 0.0,
        "power_factor": 0.0,
        "pzem_ok": pzem_ok,
    }

    now = datetime.now()
    state.update({
        "device_id": "fish-feeder-01",
        "control_mode": "telemetry_only",
        "time": clock,
        "rtc_ok": rtc_ok,
        "rssi": finite_value("wifi_rssi"),
        "feed_count_today": finite_value("feed_count_today"),
        "schedule": DEFAULT_SCHEDULE,
        "auto_feed": True,
        "next_slot_index": next_slot_index,
        "secs_to_next": secs_to_next,
        "motor": {
            "running": False,
            "state_known": False,
            "peak_current": acs_current,
            "last_takar": 0.0,
            "remaining_ms": 0,
        },
        "sensors": sensors,
    })

    billing = (
        billing_tracker.update(
            energy_value,
            settings.get("tariff_rp_per_kwh", 1444.70),
            now,
        )
        if pzem_ok
        else billing_tracker.summary(
            settings.get("tariff_rp_per_kwh", 1444.70),
            now,
        )
    )
    state.update({"billing": billing})

    snap = state.last
    history.append(snap.get("sensors", {}) or {}, snap.get("secs_to_next", 0), snap)
    alert_log.record({}, now)

    print(f"[TELEMETRY] {clock or '?'}  "
          f"AC={safe_num(sensors.get('ac_voltage')):.0f}V")
    return jsonify({"ok": True})


# ==================================================== BACA STATUS
@app.route("/api/state")
def api_state():
    """Dipanggil browser tiap 1 detik."""
    snap = state.snapshot()
    active = evaluate(snap)

    return jsonify({
        "state": snap,
        "alerts": active,
        "alert_level": worst_level(active),
        "alert_log": alert_log.recent(20),
        "settings": settings,
        "billing": billing_tracker.summary(
            settings.get("tariff_rp_per_kwh", 1444.70)
        ),
    })


@app.route("/api/history")
def api_history():
    """Data grafik. ?points=300 (max 720)."""
    try:
        points = int(request.args.get("points", settings.get("history_points", 300)))
    except ValueError:
        points = 300
    points = max(30, min(points, 720))
    return jsonify(history.series(points))


@app.route("/api/history/clear", methods=["POST"])
def api_history_clear():
    history.clear()
    return jsonify({"ok": True, "message": "History dihapus"})


def _excel_column(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _excel_cell(reference: str, value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        text = "Ya" if value else "Tidak"
    elif isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            return ""
        return f'<c r="{reference}"><v>{number:.12g}</v></c>'
    else:
        text = str(value)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)
    return (
        f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">'
        f'{escape(text)}</t></is></c>'
    )


def _build_excel(records: list[dict]) -> io.BytesIO:
    rows = [[label for _, label in EXPORT_COLUMNS]]
    rows.extend([[record.get(key) for key, _ in EXPORT_COLUMNS] for record in records])

    sheet_rows = []
    for row_index, values in enumerate(rows, start=1):
        cells = "".join(
            _excel_cell(f"{_excel_column(column_index)}{row_index}", value)
            for column_index, value in enumerate(values, start=1)
        )
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')

    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="A1:{_excel_column(len(EXPORT_COLUMNS))}{len(rows)}"/>'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        f'<autoFilter ref="A1:{_excel_column(len(EXPORT_COLUMNS))}{len(rows)}"/>'
        '</worksheet>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Data Sensor" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>',
        )
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    output.seek(0)
    return output


@app.route("/api/export.xlsx")
def api_export_excel():
    records = history.export_records()
    if not records:
        return jsonify({
            "ok": False,
            "error": "Belum ada data energi untuk diekspor",
        }), 409

    workbook = _build_excel(records)
    filename = f"AMBAFISH-data-sensor-{datetime.now():%Y%m%d-%H%M%S-%f}.xlsx"
    export_path = os.path.join(EXCEL_EXPORT_DIR, filename)
    try:
        os.makedirs(EXCEL_EXPORT_DIR, exist_ok=True)
        with open(export_path, "wb") as export_file:
            export_file.write(workbook.getvalue())
    except OSError as exc:
        app.logger.error("Gagal menyimpan ekspor Excel ke %s: %s", export_path, exc)
        return jsonify({
            "ok": False,
            "error": f"Gagal menyimpan file ke {EXCEL_EXPORT_DIR}: {exc}",
        }), 500

    workbook.seek(0)
    response = send_file(
        workbook,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
    response.headers["X-Export-Saved-To"] = export_path
    return response


# ==================================================== PERINTAH
@app.route("/api/feed_now", methods=["POST"])
def api_feed_now():
    """Tombol Feed Now di dashboard."""
    if state.snapshot().get("control_mode") == "telemetry_only":
        return jsonify({
            "ok": False,
            "error": "Firmware hanya mengirim monitoring. Beri pakan lewat Telegram.",
        }), 409

    data = request.get_json(silent=True) or {}
    try:
        takar = float(data.get("takar", 1.0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "takar harus angka"}), 400

    control_mode = state.snapshot().get("control_mode")
    max_takar = 3.3 if control_mode == "vismok" else 5.0
    if not math.isfinite(takar) or takar < 0.2 or takar > max_takar:
        return jsonify({
            "ok": False,
            "error": f"Takaran harus 0,2 sampai {max_takar} untuk firmware ini",
        }), 400

    if not state.snapshot().get("connected"):
        return jsonify({
            "ok": False,
            "error": "ESP32 tidak terhubung - perintah tidak bisa dikirim",
        }), 503

    commands.push("FEED_NOW", takar=takar)
    if control_mode == "vismok":
        state.update({
            "motor": {
                "running": True,
                "state_known": True,
                "remaining_ms": round(takar * 3000),
            },
        })
    print(f"[CMD] FEED_NOW takar={takar}")
    return jsonify({
        "ok": True,
        "message": f"Perintah feed {takar} takar diantrikan ke ESP32",
        "retry_after_ms": 30000 if control_mode == "vismok" else 4000,
    })


@app.route("/api/schedule", methods=["POST"])
def api_schedule():
    """Simpan jadwal baru (kirim ke ESP32 saat ingest berikutnya)."""
    if state.snapshot().get("control_mode") == "telemetry_only":
        return jsonify({
            "ok": False,
            "error": "Firmware tidak menerima jadwal dari dashboard. Ubah jadwal di kode ESP32.",
        }), 409

    data = request.get_json(silent=True) or {}
    slots = data.get("slots")
    enabled = bool(data.get("enabled", True))

    if not isinstance(slots, list) or not slots:
        return jsonify({"ok": False, "error": "slots harus berupa list"}), 400

    control_mode = state.snapshot().get("control_mode")
    max_takar = 3.3 if control_mode == "vismok" else 5.0
    if control_mode == "vismok" and len(slots) != 3:
        return jsonify({
            "ok": False,
            "error": "Firmware VISMOK mendukung tepat 3 slot jadwal",
        }), 400

    cleaned = []
    for slot in slots:
        try:
            time_str = str(slot.get("time", "")).strip()
            takar = float(slot.get("takar", 1.0))
            parts = time_str.split(":")
            hh, mm = int(parts[0]), int(parts[1])
        except (AttributeError, ValueError, IndexError):
            return jsonify({"ok": False, "error": f"slot tidak valid: {slot}"}), 400

        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return jsonify({"ok": False, "error": f"jam tidak valid: {time_str}"}), 400

        if not math.isfinite(takar) or takar < 0.2 or takar > max_takar:
            return jsonify({
                "ok": False,
                "error": f"Takaran harus 0,2 sampai {max_takar} untuk firmware ini",
            }), 400
        cleaned.append({"time": f"{hh:02d}:{mm:02d}", "takar": takar})

    # Periksa slot duplikat
    times = [s["time"] for s in cleaned]
    if len(times) != len(set(times)):
        return jsonify({"ok": False, "error": "ada jam yang sama lebih dari sekali"}), 400

    if not state.snapshot().get("connected"):
        # Simpan saja, akan terkirim saat ESP32 connect
        save_settings({"schedule": cleaned, "auto_feed": enabled})
        settings.update({"schedule": cleaned, "auto_feed": enabled})
        return jsonify({"ok": True, "warning": "ESP32 offline - jadwal akan dikirim saat connect"})

    commands.push("SET_SCHEDULE", slots=cleaned, enabled=enabled)
    save_settings({"schedule": cleaned, "auto_feed": enabled})
    settings.update({"schedule": cleaned, "auto_feed": enabled})

    print(f"[CMD] SET_SCHEDULE {cleaned} enabled={enabled}")
    return jsonify({"ok": True, "message": "Jadwal dikirim ke ESP32", "slots": cleaned})


@app.route("/api/settings", methods=["POST"])
def api_settings():
    """Ubah setelan lokal (tidak perlu dikirim ke ESP32)."""
    data = request.get_json(silent=True) or {}
    allowed = {"auto_feed", "base_second", "history_points"}
    filtered = {k: v for k, v in data.items() if k in allowed}
    if "tariff_rp_per_kwh" in data:
        try:
            tariff = float(data["tariff_rp_per_kwh"])
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Tarif harus berupa angka"}), 400
        if not math.isfinite(tariff) or not 1 <= tariff <= 100000:
            return jsonify({
                "ok": False,
                "error": "Tarif harus antara Rp1 dan Rp100.000 per kWh",
            }), 400
        filtered["tariff_rp_per_kwh"] = tariff
    updated = save_settings(filtered)
    settings.update(updated)
    return jsonify({"ok": True, "settings": updated})


# ==================================================== HALAMAN INFO
@app.route("/api/meta")
def api_meta():
    return jsonify({
        "metrics": [{"key": k, "label": lab, "unit": unit, "color": color}
                    for k, lab, unit, color in METRICS],
        "buffer_size": history.size,
        "defaults": DEFAULT_SETTINGS,
        "server_time": datetime.now().isoformat(timespec="seconds"),
    })


# ==================================================== JALANKAN
def get_lan_ip() -> str:
    """Cari IP LAN laptop supaya bisa ditampilkan ke user."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def open_browser_when_ready():
    """Buka browser otomatis setelah server siap."""
    time.sleep(1.5)
    try:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{PORT}")
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    lan_ip = get_lan_ip()

    print("=" * 58)
    print("  DASHBOARD PELEMPAR PAKAN IKAN")
    print("=" * 58)
    print(f"  Di laptop     : http://127.0.0.1:{PORT}")
    print(f"  Di HP (WiFi)  : http://{lan_ip}:{PORT}")
    print("=" * 58)
    print(f"  Target ESP32  : kirim ke http://{lan_ip}:{PORT}/api/telemetry")
    print(f"  History       : {history.size} titik ({history.size // 60} menit)")
    print("=" * 58)
    print("  Ctrl+C untuk berhenti\n")

    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)