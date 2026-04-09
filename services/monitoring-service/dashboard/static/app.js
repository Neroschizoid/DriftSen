const monitoringBase = `${window.location.origin}/api/v1/monitoring`;
let inferenceBase = `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;

const monitorStatusEl = document.getElementById("monitor-status");
const inferenceStatusEl = document.getElementById("inference-status");
const kafkaStatusEl = document.getElementById("kafka-status");
const driftScoreEl = document.getElementById("drift-score");
const severityLabelEl = document.getElementById("severity-label");
const gaugeNeedleEl = document.getElementById("gauge-needle");
const latencyLiveEl = document.getElementById("latency-live");
const latencyAvgEl = document.getElementById("latency-avg");
const latencyMinEl = document.getElementById("latency-min");
const latencyMaxEl = document.getElementById("latency-max");
const driftMethodEl = document.getElementById("drift-method");
const windowFillEl = document.getElementById("window-fill");
const driftedCountEl = document.getElementById("drifted-count");
const featureCountEl = document.getElementById("feature-count");
const featureHeatmapEl = document.getElementById("feature-heatmap");
const eventFeedEl = document.getElementById("event-feed");
const lastUpdatedEl = document.getElementById("last-updated");

const probeBtn = document.getElementById("probe-btn");
const customSendBtn = document.getElementById("custom-send-btn");
const customFeaturesEl = document.getElementById("custom-features");
const modeSelectEl = document.getElementById("mode-select");
const modeStepsEl = document.getElementById("mode-steps");
const modeIntervalEl = document.getElementById("mode-interval");
const modeStartBtn = document.getElementById("mode-start-btn");
const modeStopBtn = document.getElementById("mode-stop-btn");
const modeStatusEl = document.getElementById("mode-status");
const refreshBtn = document.getElementById("refresh-btn");
const liveStartBtn = document.getElementById("live-start-btn");
const liveStopBtn = document.getElementById("live-stop-btn");
const liveStatusEl = document.getElementById("live-status");

const cmdHealthBtn = document.getElementById("cmd-health-btn");
const cmdInferBtn = document.getElementById("cmd-infer-btn");
const cmdDriftBtn = document.getElementById("cmd-drift-btn");
const cmdGradualBtn = document.getElementById("cmd-gradual-btn");
const cmdSuddenBtn = document.getElementById("cmd-sudden-btn");
const cmdNormalBtn = document.getElementById("cmd-normal-btn");
const cmdAuditBtn = document.getElementById("cmd-audit-btn");
const cmdUnitBtn = document.getElementById("cmd-unit-btn");
const cmdKafkaBtn = document.getElementById("cmd-kafka-btn");
const cmdShutdownBtn = document.getElementById("cmd-shutdown-btn");
const cmdResetBtn = document.getElementById("cmd-reset-btn");

const state = {
  trendLabels: [],
  trendScores: [],
  trendMax: 40,
  latency: [],
  logs: [],
  liveTimer: null,
  statusTimer: null,
};

let chart = null;
if (typeof Chart !== "undefined") {
  chart = new Chart(document.getElementById("driftChart"), {
    type: "line",
    data: {
      labels: state.trendLabels,
      datasets: [{
        data: state.trendScores,
        borderColor: "#4bb6ff",
        backgroundColor: "rgba(75, 182, 255, 0.12)",
        fill: true,
        pointRadius: 0,
        tension: 0.3,
      }],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#9db1cb" }, grid: { color: "rgba(157,177,203,0.12)" } },
        y: { min: 0, max: 1, ticks: { color: "#9db1cb" }, grid: { color: "rgba(157,177,203,0.12)" } },
      },
    },
  });
}

function setPill(el, text, level) {
  el.textContent = text;
  el.className = `pill ${level || ""}`.trim();
}

function setSeverity(score, severity) {
  const s = String(severity || "NONE").toUpperCase();
  const clamped = Math.max(0, Math.min(1, Number(score || 0)));
  const angle = -90 + (clamped * 180);
  gaugeNeedleEl.style.transform = `translateX(-50%) rotate(${angle}deg)`;
  severityLabelEl.textContent = s;
  severityLabelEl.className = "badge";
  if (s === "LOW") severityLabelEl.classList.add("low");
  if (s === "MEDIUM") severityLabelEl.classList.add("medium");
  if (s === "HIGH") severityLabelEl.classList.add("high");
}

function updateTrend(score, whenIso) {
  state.trendLabels.push(new Date(whenIso || Date.now()).toLocaleTimeString());
  state.trendScores.push(Number(score || 0));
  if (state.trendLabels.length > state.trendMax) {
    state.trendLabels.shift();
    state.trendScores.shift();
  }
  if (chart) chart.update("none");
}

function renderLogs(lines) {
  state.logs = lines || [];
  eventFeedEl.innerHTML = "";
  for (const item of state.logs.slice().reverse()) {
    const row = document.createElement("div");
    const level = item.includes("❌") || item.includes("failed") ? "bad"
      : item.includes("WARNING") || item.includes("🔴") ? "warn"
      : "";
    row.className = `feed-item ${level}`.trim();
    row.textContent = item;
    eventFeedEl.appendChild(row);
  }
}

function updateHeatmap(featureReport) {
  featureHeatmapEl.innerHTML = "";
  if (!Array.isArray(featureReport) || featureReport.length === 0) {
    const n = document.createElement("div");
    n.className = "feature-chip";
    n.textContent = "No feature report yet.";
    featureHeatmapEl.appendChild(n);
    featureCountEl.textContent = "0";
    return;
  }

  const sorted = [...featureReport].sort((a, b) => {
    const av = a.ks_statistic ?? a.z_score ?? 0;
    const bv = b.ks_statistic ?? b.z_score ?? 0;
    return bv - av;
  });

  const drifted = sorted.filter((f) => f.drift_detected);
  featureCountEl.textContent = String(drifted.length);
  const view = drifted.length ? drifted : sorted.slice(0, 16);

  for (const f of view) {
    const chip = document.createElement("div");
    chip.className = `feature-chip ${f.drift_detected ? "hot" : ""}`;
    const metric = f.ks_statistic !== undefined
      ? `KS ${Number(f.ks_statistic).toFixed(3)}`
      : `Z ${Number(f.z_score ?? 0).toFixed(2)}`;
    chip.innerHTML = `<strong>${f.feature}</strong><br><span class="mono">${metric}</span>`;
    featureHeatmapEl.appendChild(chip);
  }
}

async function apiGet(path) {
  const r = await fetch(`${monitoringBase}${path}`);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

async function apiPost(path, payload = {}) {
  const r = await fetch(`${monitoringBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`${path} -> ${r.status} ${t}`);
  }
  return r.json();
}

async function refreshSnapshot() {
  try {
    const [cfg, drift, win] = await Promise.all([
      apiGet("/config"),
      apiGet("/drift"),
      apiGet("/window"),
    ]);

    setPill(monitorStatusEl, "Monitoring: Online", "ok");
    setPill(kafkaStatusEl, `Kafka: ${cfg.kafka_enabled ? "Enabled" : "Fallback(Log)"}`, cfg.kafka_enabled ? "ok" : "warn");
    driftMethodEl.textContent = String(cfg.drift_method || "--").toUpperCase();
    if (cfg.inference_url) {
      inferenceBase = String(cfg.inference_url).replace(/\/+$/, "");
    }

    const score = Number(drift.drift_score || 0);
    driftScoreEl.textContent = score.toFixed(4);
    setSeverity(score, drift.drift_detected ? drift.drift_severity : "NONE");
    updateTrend(score, drift.computed_at);
    updateHeatmap(drift.feature_report || []);

    const current = Number(win.current_window_size || 0);
    const max = Number(win.max_window_size || 100);
    windowFillEl.textContent = `${current} / ${max}`;
    driftedCountEl.textContent = `${drift.features_drifted || 0} / ${drift.features_checked || 0}`;
    lastUpdatedEl.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
  } catch (e) {
    setPill(monitorStatusEl, "Monitoring: Offline", "bad");
  }

  await checkInferenceLatency();
}

async function checkInferenceLatency() {
  const t0 = performance.now();
  try {
    const r = await fetch(`${inferenceBase}/health`);
    if (!r.ok) throw new Error(String(r.status));
    const ms = performance.now() - t0;
    state.latency.push(ms);
    if (state.latency.length > 40) state.latency.shift();
    const avg = state.latency.reduce((a, b) => a + b, 0) / state.latency.length;

    latencyLiveEl.textContent = `${ms.toFixed(1)} ms`;
    latencyAvgEl.textContent = `${avg.toFixed(1)} ms`;
    latencyMinEl.textContent = `${Math.min(...state.latency).toFixed(1)} ms`;
    latencyMaxEl.textContent = `${Math.max(...state.latency).toFixed(1)} ms`;
    setPill(inferenceStatusEl, "Inference: Online", "ok");
  } catch (e) {
    setPill(inferenceStatusEl, "Inference: Offline", "bad");
  }
}

async function pollDemoStatus() {
  try {
    const s = await apiGet("/demo/status?lines=200");
    modeStatusEl.textContent = s.running
      ? `${String(s.mode).toUpperCase()} ${s.progress}/${s.iterations}`
      : "Idle";
    renderLogs(s.logs || []);
  } catch (e) {
    // ignore transient failures
  }
}

function startLiveMode() {
  if (state.liveTimer) return;
  liveStatusEl.textContent = "Live mode: ON (4s interval)";
  state.liveTimer = setInterval(refreshSnapshot, 4000);
}

function stopLiveMode() {
  if (state.liveTimer) {
    clearInterval(state.liveTimer);
    state.liveTimer = null;
  }
  liveStatusEl.textContent = "Live mode: OFF";
}

async function runCommand(command) {
  await apiPost("/demo/command", { command });
  await pollDemoStatus();
}

async function runMode(mode) {
  await apiPost("/demo/run", {
    mode,
    iterations: Number(modeStepsEl.value || 60),
    interval_ms: Number(modeIntervalEl.value || 300),
  });
  await pollDemoStatus();
}

modeStartBtn.addEventListener("click", () => runMode(modeSelectEl.value).catch(console.error));
modeStopBtn.addEventListener("click", () => apiPost("/demo/stop").catch(console.error));

probeBtn.addEventListener("click", async () => {
  const payload = { dur: 0.5, spkts: 3.0, dpkts: 2.0, rate: 1000 };
  const r = await fetch(`${inferenceBase}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ features: payload }),
  });
  if (!r.ok) console.error("probe failed");
  await refreshSnapshot();
});

customSendBtn.addEventListener("click", async () => {
  try {
    const parsed = JSON.parse(customFeaturesEl.value);
    await fetch(`${inferenceBase}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ features: parsed }),
    });
    await refreshSnapshot();
  } catch (e) {
    console.error(e);
  }
});

refreshBtn.addEventListener("click", () => refreshSnapshot().catch(console.error));
liveStartBtn.addEventListener("click", startLiveMode);
liveStopBtn.addEventListener("click", stopLiveMode);

cmdHealthBtn.addEventListener("click", () => runCommand("verify_health").catch(console.error));
cmdInferBtn.addEventListener("click", () => runCommand("inference_sample").catch(console.error));
cmdDriftBtn.addEventListener("click", () => runCommand("show_drift").catch(console.error));
cmdGradualBtn.addEventListener("click", () => runMode("gradual").catch(console.error));
cmdSuddenBtn.addEventListener("click", () => runMode("sudden").catch(console.error));
cmdNormalBtn.addEventListener("click", () => runMode("normal").catch(console.error));
cmdAuditBtn.addEventListener("click", () => runCommand("show_audit_logs").catch(console.error));
cmdUnitBtn.addEventListener("click", () => runCommand("unit_tests").catch(console.error));
cmdKafkaBtn.addEventListener("click", () => runCommand("kafka_integration_test").catch(console.error));
cmdShutdownBtn.addEventListener("click", () => runCommand("shutdown_stack").catch(console.error));
cmdResetBtn.addEventListener("click", async () => {
  await apiPost("/reset_state", {});
  await refreshSnapshot();
  await pollDemoStatus();
});

(async function init() {
  await refreshSnapshot();
  await pollDemoStatus();
  state.statusTimer = setInterval(pollDemoStatus, 2000);
  stopLiveMode();
})();
