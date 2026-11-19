/* =====================================================================
   app.js - Logika dashboard Pelempar Pakan Ikan
   ---------------------------------------------------------------------
   - Poll /api/state tiap 1 detik
   - Poll /api/history tiap 2 detik untuk grafik
   - Kirim perintah lewat POST (diantar ESP32 saat ingest berikutnya)
   ===================================================================== */

/* ---------------------------------------------------------------- state */
const app = {
  chart: null,
  currentMetric: 'ac_voltage',
  latest: null,
  pollTimer: null,
  histTimer: null,
  knownAlerts: new Set(),   // untuk deteksi alert baru
  schedule: [
    { time: "07:00", takar: 1.0 },
    { time: "12:00", takar: 1.0 },
    { time: "17:00", takar: 1.0 },
  ],
  autoFeed: true,
  baseSecond: 3.0,
  feedCooldownUntil: 0,
};

const $ = (id) => document.getElementById(id);

/* =====================================================================
   FORMAT
   ===================================================================== */
function fmt(v, d = 1) {
  if (v === null || v === undefined || isNaN(v)) return "--";
  return Number(v).toFixed(d);
}

function fmtUptime(ms) {
  if (!ms) return "--";
  const s = Math.floor(ms / 1000);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}h ${h}j ${m}m`;
  if (h > 0) return `${h}j ${m}m`;
  return `${m}m ${s % 60}d`;
}

function formatRupiah(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "--";
  return `Rp ${Math.round(Number(value)).toLocaleString("id-ID")}`;
}

function renderBilling(billing, settings) {
  if (!billing) return;
  const tariff = settings?.tariff_rp_per_kwh ?? billing.tariff_rp_per_kwh;
  if (document.activeElement !== $("tariffInput")) {
    $("tariffInput").value = Number(tariff).toFixed(2);
  }

  $("billTodayKwh").textContent = `${fmt(billing.today_kwh, 3)} kWh`;
  $("billTodayCost").textContent = formatRupiah(billing.today_cost_rp);
  $("billMonthKwh").textContent = `${fmt(billing.month_kwh, 3)} kWh`;
  $("billMonthCost").textContent = formatRupiah(billing.month_cost_rp);
  $("billProjection").textContent = formatRupiah(billing.projected_month_cost_rp);
  $("billProjectionKwh").textContent =
    `${fmt(billing.projected_month_kwh, 2)} kWh proyeksi bulan ini`;

  $("billingNote").textContent = billing.has_baseline
    ? `Tarif Rp ${Number(tariff).toLocaleString("id-ID")}/kWh. Proyeksi memakai rata-rata sejak pemantauan bulan ini dimulai${billing.projected_month_cost_rp === null ? " dan tersedia setelah minimal 1 hari data" : ""}. Pencatatan delta dimulai ${billing.started_at || "saat pembacaan pertama"}; hanya untuk beban pada PZEM, belum termasuk pajak/biaya PLN.`
    : "Menunggu pembacaan energi PZEM pertama sebagai titik awal. Konsumsi dan estimasi akan bertambah setelah ada selisih pembacaan; hanya untuk beban yang diukur, bukan total tagihan rumah.";
}

function countdownText(totalSec) {
  if (totalSec === null || totalSec === undefined) return "Jadwal belum diatur";
  const s = Math.max(0, Math.floor(totalSec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const d = s % 60;
  if (h > 0) return `${h} jam ${m} menit lagi`;
  if (m > 0) return `${m} menit ${d} detik lagi`;
  return `${d} detik lagi`;
}

/* =====================================================================
   TOAST
   ===================================================================== */
let toastTimer = null;
function toast(msg, kind = "") {
  const el = $("toast");
  el.textContent = msg;
  el.className = "toast " + kind;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 3200);
}

/* =====================================================================
   RENDER STATE
   ===================================================================== */
function renderState(data) {
  const s = data.state;
  const sensors = s.sensors || {};
  const motor = s.motor || {};
  app.latest = data;
  renderBilling(data.billing, data.settings);

  /* --- koneksi --- */
  const on = s.connected;
  $("connDot").className = "dot " + (on ? "dot-on" : "dot-off");
  $("connText").textContent = on ? "ESP32 online" : "ESP32 offline";
  $("deviceId").textContent = s.device_id || "fish-feeder-01";

  /* --- jam --- */
  if (s.time) {
    $("clockTime").textContent = s.time.includes("T")
      ? (s.time.split("T")[1] || "--:--:--")
      : s.time;
  } else {
    $("clockTime").textContent = "--:--:--";
  }
  const rtcBadge = $("rtcBadge");
  rtcBadge.textContent = s.rtc_ok ? "RTC OK" : "RTC ?";
  rtcBadge.className = "badge " + (s.rtc_ok ? "badge-ok" : "badge-err");

  /* --- next feed --- */
  const idx = s.next_slot_index;
  const sched = s.schedule || [];
  if (idx >= 0 && sched[idx]) {
    $("nextTime").textContent = sched[idx].time;
    $("nextSlotName").textContent = `Slot ${idx + 1} · ${sched[idx].takar} takar`;
  } else {
    $("nextTime").textContent = "--:--";
    $("nextSlotName").textContent = "Tidak ada slot aktif";
  }
  $("nextCountdown").textContent = countdownText(s.secs_to_next);

  /* --- motor --- */
  const running = motor.running;
  const pill = $("motorPill");
  pill.className = "motor-pill" + (running ? " running" : "");
  if (motor.state_known === false) {
    $("motorStatus").textContent = "Status motor tidak dikirim firmware";
  } else if (running) {
    const rem = (motor.remaining_ms || 0) / 1000;
    $("motorStatus").textContent = `Motor jalan · ${fmt(rem, 1)}s tersisa`;
  } else {
    $("motorStatus").textContent = motor.last_takar
      ? `Idle · terakhir ${fmt(motor.last_takar, 1)} takar`
      : "Motor idle";
  }

  /* --- gauge --- */
  $("gAcVolt").textContent    = fmt(sensors.ac_voltage, 0);
  $("gPower").textContent     = fmt(sensors.power_w, 1);
  $("gAcCur").textContent     = fmt(sensors.ac_current, 2);
  $("gEnergy").textContent    = fmt(sensors.energy_wh, 1);
  const motorCurrent = s.control_mode === "capstone" || motor.state_known === false
    ? sensors.motor_current
    : (motor.running ? sensors.motor_current : sensors.peak_current);
  $("gMotorCur").textContent = fmt(motorCurrent, 2);
  $("gRssi").textContent      = fmt(s.rssi, 0);
  $("gFeedCount").textContent = fmt(s.feed_count_today, 0);

  /* kualitas sinyal WiFi */
  const rssi = Number(s.rssi) || 0;
  const q = $("gRssiQ");
  if (rssi >= -55)      { q.textContent = "ESP32 · bagus";      q.style.color = "#34d399"; }
  else if (rssi >= -67) { q.textContent = "ESP32 · cukup";      q.style.color = "#fbbf24"; }
  else if (rssi >= -72) { q.textContent = "ESP32 · lemah";      q.style.color = "#fb923c"; }
  else                  { q.textContent = "ESP32 · sangat lemah"; q.style.color = "#f87171"; }

  /* --- detail sensor --- */
  $("dZmptRaw").textContent   = fmt(sensors.zmtp_raw, 3) + " V";
  $("dZmpt").textContent      = fmt(sensors.zmtp_voltage, 1) + " V";
  $("dBaseline").textContent  = fmt(sensors.acs_baseline, 3) + " V";
  $("dPeak").textContent      = fmt(
    s.control_mode === "capstone" || motor.state_known === false
      ? sensors.motor_current
      : sensors.peak_current,
    3
  ) + " A";
  $("dFreq").textContent      = fmt(sensors.freq, 1) + " Hz";
  $("dPf").textContent        = fmt(sensors.power_factor, 2);
  $("dPzemOk").textContent    = sensors.pzem_ok ? "Terbaca" : "Tidak terbaca";
  $("dHeap").textContent      = s.free_heap ? Math.round(s.free_heap / 1024) + " KB" : "--";
  $("dUptime").textContent    = fmtUptime(s.uptime_ms);

  /* --- alert banner --- */
  renderAlerts(data.alerts || [], data.alert_level);

  /* --- sync jadwal dari ESP32 --- */
  if (sched.length === 3 && !document.activeElement?.closest("#schedBody")) {
    if (JSON.stringify(sched) !== JSON.stringify(app.schedule)) {
      app.schedule = sched.map((x) => ({ time: x.time, takar: x.takar }));
      renderScheduleTable();
    }
  }
  if (s.auto_feed !== undefined && $("autoFeed").checked !== s.auto_feed) {
    app.autoFeed = s.auto_feed;
    $("autoFeed").checked = s.auto_feed;
  }

  const telemetryOnly = s.control_mode === "telemetry_only";
  const capstone = s.control_mode === "capstone";
  ["dZmptRawRow", "dBaselineRow", "dFreqRow", "dPfRow"]
    .forEach((id) => { $(id).hidden = telemetryOnly || capstone; });
  ["dHeapRow", "dUptimeRow"].forEach((id) => { $(id).hidden = telemetryOnly; });
  $("btnFeedNow").disabled = telemetryOnly || Date.now() < app.feedCooldownUntil;
  $("btnFeedNow").textContent = telemetryOnly ? "Kontrol via Telegram" : "🍽 Feed Sekarang";
  $("btnFeedNow").title = telemetryOnly
    ? "Firmware saat ini hanya mengirim monitoring; gunakan Telegram untuk memberi pakan."
    : "";
  $("btnSaveSched").disabled = telemetryOnly;
  $("autoFeed").disabled = telemetryOnly;
  $("takarInput").disabled = telemetryOnly;
  $("takarInput").max = capstone ? "3.3" : "5";
  for (let i = 0; i < 3; i++) {
    const timeInput = $(`time-${i}`);
    const takarInput = $(`takar-${i}`);
    if (timeInput) timeInput.disabled = telemetryOnly;
    if (takarInput) {
      takarInput.disabled = telemetryOnly;
      takarInput.max = capstone ? "3.3" : "5";
    }
  }
  $("scheduleHint").textContent = telemetryOnly
    ? "Jadwal tetap 07:00, 12:00, 17:00; ubah di kode firmware ESP32."
    : capstone
      ? "Kontrol tersambung ke firmware capstone · 1 takar ≈ 3 detik (maks. 10 detik)."
    : "Durasi = 3 detik · takaran";
}

/* =====================================================================
   ALERT
   ===================================================================== */
function renderAlerts(alerts, level) {
  const banner = $("alertBanner");

  if (!alerts.length) {
    banner.classList.add("hidden");
    banner.className = "alert-banner hidden";
  } else {
    const top = alerts.find((a) => a.level === "error") || alerts[0];
    banner.classList.remove("hidden");
    banner.className = "alert-banner lv-" + (top.level === "error" ? "err" : top.level);
    $("alertTitle").textContent =
      alerts.length > 1 ? `${alerts.length} peringatan aktif` : top.code;
    $("alertMessage").textContent = alerts.map((a) => a.message).join(" · ");
  }

  /* bunyi + toast untuk alert BARU saja */
  const now = new Set(alerts.map((a) => a.code));
  alerts.forEach((a) => {
    if (!app.knownAlerts.has(a.code)) {
      app.knownAlerts.add(a.code);
      if (app.knownAlerts.size > 1 || a.level !== "info") {
        toast(`${a.code}: ${a.message}`, "err");
        beep();
      }
    }
  });
  app.knownAlerts = now;
}

/* beep singkat pakai Web Audio (tidak perlu file) */
let audioCtx = null;
function beep() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "sine";
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.35);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.35);
  } catch (e) {
    /* audio tidak tersedia, abaikan */
  }
}

/* =====================================================================
   JADWAL
   ===================================================================== */
function renderScheduleTable() {
  const body = $("schedBody");
  const nextIdx = app.latest?.state?.next_slot_index ?? -1;
  const secsNext = app.latest?.state?.secs_to_next ?? 0;

  body.innerHTML = "";
  app.schedule.forEach((slot, i) => {
    const dur = (app.baseSecond * slot.takar).toFixed(1);

    let state = "slot-idle";
    let label = "Menunggu";
    if (i === nextIdx) {
      state = "slot-next";
      label = countdownText(secsNext).replace(" lagi", "");
    }

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>Slot ${i + 1}</strong></td>
      <td><input type="time" id="time-${i}" value="${slot.time}"></td>
      <td><input type="number" id="takar-${i}" value="${slot.takar}"
                 min="0.2" max="5" step="0.1"></td>
      <td class="durasi-cell">${dur}s</td>
      <td><span class="slot-state ${state}">${label}</span></td>
    `;
    body.appendChild(tr);

    // update durasi saat user ubah takaran
    $(`takar-${i}`).addEventListener("input", (e) => {
      const t = parseFloat(e.target.value) || 0;
      tr.querySelector(".durasi-cell").textContent = (app.baseSecond * t).toFixed(1) + "s";
    });
  });
}

async function saveSchedule() {
  const slots = [];
  for (let i = 0; i < 3; i++) {
    slots.push({
      time: $(`time-${i}`).value,
      takar: parseFloat($(`takar-${i}`).value) || 1.0,
    });
  }
  const btn = $("btnSaveSched");
  btn.disabled = true;
  btn.textContent = "Mengirim...";
  try {
    const res = await fetch("/api/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slots, enabled: $("autoFeed").checked }),
    });
    const json = await res.json();
    if (json.ok) {
      app.schedule = slots;
      toast(json.warning || "Jadwal disimpan", "ok");
    } else {
      toast(json.error || "Gagal menyimpan jadwal", "err");
    }
  } catch (e) {
    toast("Tidak bisa menghubungi server", "err");
  } finally {
    btn.disabled = false;
    btn.textContent = "Simpan Jadwal";
  }
}

/* =====================================================================
   FEED NOW
   ===================================================================== */
async function feedNow() {
  const takar = parseFloat($("takarInput").value) || 1.0;
  const btn = $("btnFeedNow");
  btn.disabled = true;
  try {
    const res = await fetch("/api/feed_now", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ takar }),
    });
    const json = await res.json();
    if (json.ok) {
      toast(json.message, "ok");
      const cooldown = json.retry_after_ms || 4000;
      app.feedCooldownUntil = Date.now() + cooldown;
      setTimeout(() => {
        app.feedCooldownUntil = 0;
        btn.disabled = app.latest?.state?.control_mode === "telemetry_only";
      }, cooldown);
    } else {
      toast(json.error || "Perintah gagal", "err");
      btn.disabled = false;
    }
  } catch (e) {
    toast("Tidak bisa menghubungi server", "err");
    btn.disabled = false;
  }
}

/* =====================================================================
   GRAFIK
   ===================================================================== */
function initChart() {
  const ctx = document.getElementById("mainChart").getContext("2d");

  /* warna grid & teks konsisten dengan tema */
  const gridC = "rgba(148, 163, 184, 0.07)";
  const tickC = "#67748b";

  Chart.defaults.font.family =
    '"JetBrains Mono", "Cascadia Mono", Consolas, ui-monospace, monospace';
  Chart.defaults.font.size = 10;

  app.chart = new Chart(ctx, {
    type: "line",
    data: { labels: [], datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      animation: { duration: 400, easing: "easeOutQuart" },
      layout: { padding: { top: 4, right: 4, left: 0, bottom: 0 } },
      plugins: {
        legend: {
          display: true,
          position: "top",
          align: "end",
          labels: {
            usePointStyle: true,
            pointStyle: "circle",
            boxWidth: 6,
            boxHeight: 6,
            padding: 16,
            color: "#9dabc2",
            font: { size: 11, family: '"Plus Jakarta Sans", "Segoe UI", Inter, system-ui, sans-serif' },
          },
        },
        tooltip: {
          backgroundColor: "rgba(22, 29, 43, 0.94)",
          borderColor: "rgba(148, 163, 184, 0.18)",
          borderWidth: 1,
          titleColor: "#e9eef8",
          bodyColor: "#9dabc2",
          padding: { top: 10, bottom: 10, left: 14, right: 14 },
          cornerRadius: 10,
          displayColors: true,
          usePointStyle: true,
          boxWidth: 6,
          boxHeight: 6,
          boxPadding: 5,
          titleFont: { size: 10.5, weight: "600" },
          bodyFont: { size: 11 },
          titleSpacing: 2,
          bodySpacing: 4,
        },
      },
      scales: {
        x: {
          ticks: { color: tickC, maxTicksLimit: 8, maxRotation: 0, autoSkip: true },
          grid: { color: gridC, drawTicks: false },
          border: { display: false },
        },
        y: {
          ticks: { color: tickC, maxTicksLimit: 6, padding: 8 },
          grid: { color: gridC, drawTicks: false },
          border: { display: false },
          beginAtZero: false,
          grace: "8%",
        },
      },
    },
  });
}

async function refreshChart() {
  const points = $("rangeSelect").value;
  try {
    const res = await fetch(`/api/history?points=${points}`);
    const data = await res.json();

    const keys =
      app.currentMetric === "all"
        ? Object.keys(data.series)
        : [app.currentMetric];

    const isSingle = keys.length === 1;

    const datasets = keys
      .filter((k) => data.series[k] && data.series[k].length)
      .map((k) => {
        const meta = data.meta[k] || {};
        const color = meta.color || "#60a5fa";

        /* isi gradasi hanya saat satu metrik ditampilkan */
        const fillFn = isSingle
          ? (c) => {
              const { ctx, chartArea } = c.chart;
              if (!chartArea) return "transparent";
              const g = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              g.addColorStop(0, color + "4d");
              g.addColorStop(0.55, color + "1a");
              g.addColorStop(1, color + "00");
              return g;
            }
          : "rgba(0,0,0,0)";

        return {
          label: meta.label ? `${meta.label}${meta.unit ? " (" + meta.unit + ")" : ""}` : k,
          data: data.series[k],
          borderColor: color,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 3.5,
          pointHoverBorderWidth: 2,
          tension: 0.32,
          backgroundColor: fillFn,
          fill: isSingle,
        };
      });

    app.chart.data.labels = data.labels;
    app.chart.data.datasets = datasets;
    app.chart.update("none");
  } catch (e) {
    /* server belum siap, coba lagi nanti */
  }
}

async function exportExcel() {
  const btn = $("btnExportExcel");
  btn.disabled = true;
  try {
    const response = await fetch("/api/export.xlsx", { cache: "no-store" });
    if (!response.ok) {
      const error = await response.json();
      toast(error.error || "Gagal mengekspor data", "err");
      return;
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const disposition = response.headers.get("Content-Disposition") || "";
    const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1];
    link.download = filename || "AMBAFISH-data-sensor.xlsx";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("File Excel terunduh dan disimpan di D:\\CAPSTONE", "ok");
  } catch (error) {
    toast("Tidak bisa mengunduh file Excel", "err");
  } finally {
    btn.disabled = false;
  }
}

async function saveTariff() {
  const input = $("tariffInput");
  const tariff = Number(input.value);
  if (!Number.isFinite(tariff) || tariff < 1 || tariff > 100000) {
    toast("Tarif harus antara Rp1 dan Rp100.000 per kWh", "err");
    return;
  }

  const button = $("btnSaveTariff");
  button.disabled = true;
  try {
    const response = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tariff_rp_per_kwh: tariff }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      toast(result.error || "Gagal menyimpan tarif", "err");
      return;
    }
    toast("Tarif listrik berhasil disimpan", "ok");
    await pollState();
  } catch (error) {
    toast("Tidak bisa menyimpan tarif ke server", "err");
  } finally {
    button.disabled = false;
  }
}

/* =====================================================================
   RIWAYAT ALERT
   ===================================================================== */
function renderAlertLog(items) {
  const ul = $("alertList");
  if (!items || !items.length) {
    ul.innerHTML = '<li class="empty">Belum ada peringatan</li>';
    return;
  }
  ul.innerHTML = items
    .map(
      (a) => `<li class="${a.status === "resolved" ? "resolved" : "error"}">
                <span class="t">${a.time}</span>
                <span class="m">${a.message || a.code}</span>
              </li>`
    )
    .join("");
}

/* =====================================================================
   POLLING
   ===================================================================== */
let lastLogSignature = "";

async function pollState() {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    const data = await res.json();
// tampilkan halaman begitu data pertama berhasil masuk
    renderState(data);
    showReady();

    // riwayat alert cukup diperbarui kalau berubah
    const sig = JSON.stringify((data.alert_log || []).slice(0, 5));
    if (sig !== lastLogSignature) {
      lastLogSignature = sig;
      renderAlertLog(data.alert_log);
    }
  } catch (e) {
    $("connDot").className = "dot dot-off";
    $("connText").textContent = "Server tidak merespons";
  }
}

/* =====================================================================
   INIT
   ===================================================================== */
function init() {
  initChart();
  renderScheduleTable();
  pollState();
  refreshChart();

  /* konten tampil halus begitu data pertama masuk (maks 2.5 dtk) */
  setTimeout(showReady, 2500);

  app.pollTimer = setInterval(pollState, 1000);
  app.histTimer = setInterval(() => {
    if ($("autoRefresh").checked) refreshChart();
  }, 2000);

  /* event */
  $("btnFeedNow").addEventListener("click", feedNow);
  $("btnSaveSched").addEventListener("click", saveSchedule);
  $("btnSaveTariff").addEventListener("click", saveTariff);
  $("btnExportExcel").addEventListener("click", exportExcel);
  $("rangeSelect").addEventListener("change", refreshChart);

  $("btnClearHist").addEventListener("click", async () => {
    await fetch("/api/history/clear", { method: "POST" });
    toast("History grafik dihapus");
    refreshChart();
  });

  $("autoFeed").addEventListener("change", async (e) => {
    const enabled = e.target.checked;
    const slots = [];
    for (let i = 0; i < 3; i++) {
      slots.push({
        time: $(`time-${i}`).value,
        takar: parseFloat($(`takar-${i}`).value) || 1.0,
      });
    }
    try {
      await fetch("/api/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slots, enabled }),
      });
      toast(enabled ? "Mode otomatis aktif" : "Mode otomatis dimatikan", "ok");
    } catch (err) {
      toast("Gagal mengubah mode", "err");
    }
  });

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      app.currentMetric = tab.dataset.metric;
      refreshChart();
    });
  });

  /* tombol untuk tes alert (opsional, berguna saat commissioning) */
  window.__fishfeeder = { app, toast, beep };
}

document.addEventListener("DOMContentLoaded", init);

/* animasi kemunculan halaman saat pertama tampil.
   Fallback timeout supaya konten tidak pernah tertutup selamanya. */
let _readyShown = false;
function showReady() {
  if (_readyShown) return;
  _readyShown = true;
  document.body.classList.add("ready");
}