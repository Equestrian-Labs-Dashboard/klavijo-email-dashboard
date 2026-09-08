const CHART_COLORS = {
  indigo: "#4F5BD5",
  sage: "#1E9E6B",
  clay: "#E24C3D",
};

function themeColor(varName) {
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
}

const fmtUSD = (n) => n === null || n === undefined ? "—" : "$" + Math.round(n).toLocaleString("en-US");
const fmtInt = (n) => n === null || n === undefined ? "—" : Math.round(n).toLocaleString("en-US");
const fmtPct = (n, digits = 1) => n === null || n === undefined ? "—" : `${n.toFixed(digits)}%`;
const fmtUSD2 = (n) => n === null || n === undefined ? "—" : "$" + n.toFixed(2);

function pctChange(curr, prev) {
  if (prev === null || prev === undefined || prev === 0 || curr === null || curr === undefined) return null;
  return ((curr - prev) / Math.abs(prev)) * 100;
}

function getByPath(obj, path) {
  return path.split(".").reduce((acc, key) => (acc ? acc[key] : undefined), obj);
}

function setPill(el, value, { digits = 1, suffix = " vs prev." } = {}) {
  if (value === null || value === undefined) {
    el.textContent = "—";
    el.className = "pill is-neutral";
    return;
  }
  const arrow = value >= 0 ? "▲" : "▼";
  el.textContent = `${arrow} ${Math.abs(value).toFixed(digits)}%${suffix}`;
  el.className = "pill " + (value >= 0 ? "" : "is-negative");
}

async function loadData() {
  const res = await fetch("data/data.json", { cache: "no-store" });
  if (!res.ok) throw new Error("Could not load data/data.json");
  return res.json();
}

// ---- Theme toggle ----
function initTheme() {
  const saved = localStorage.getItem("klaviyo-dashboard-theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = saved || (prefersDark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);

  document.getElementById("theme-toggle").addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("klaviyo-dashboard-theme", next);
    if (window.__redrawCharts) window.__redrawCharts();
  });
}

// ---- Month filter ----
function populateMonthSelect(data) {
  const select = document.getElementById("month-select");
  select.innerHTML = data.months.map((m, i) => `<option value="${i}">${m}</option>`).join("");
  select.value = data.months.length - 1; // default to latest month
  return select;
}

function quarterIndices(monthIdx) {
  // group months into quarters of 3, aligned to the start of the dataset
  const qStart = Math.floor(monthIdx / 3) * 3;
  return [qStart, Math.min(qStart + 2, monthIdx)];
}

let charts = {};

function destroyChart(key) {
  if (charts[key]) { charts[key].destroy(); delete charts[key]; }
}

function lineChart(canvasId, labels, series, color, fill = false) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  charts[canvasId] = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        data: series,
        borderColor: color,
        backgroundColor: fill ? color + "1f" : "transparent",
        fill,
        tension: 0.35,
        pointRadius: 0,
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: themeColor("--muted"), font: { size: 11 } } },
        y: { grid: { color: themeColor("--line") }, ticks: { color: themeColor("--muted"), font: { size: 11 } } },
      },
    },
  });
}

function sparkline(canvasId, series, color) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  charts[canvasId] = new Chart(ctx, {
    type: "line",
    data: {
      labels: series.map((_, i) => i),
      datasets: [{ data: series, borderColor: color, borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: false }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
    },
  });
}

function renderHero(data, idx) {
  const curr = data.gross_sales[idx];
  const prev = idx > 0 ? data.gross_sales[idx - 1] : null;
  document.getElementById("hero-gross-sales").textContent = fmtUSD(curr);
  setPill(document.getElementById("hero-delta"), pctChange(curr, prev));
  document.getElementById("last-updated").textContent = data.meta.last_updated;
  document.getElementById("footer-note").textContent = data.meta.note;
  lineChart("grossSalesChart", data.months.slice(0, idx + 1), data.gross_sales.slice(0, idx + 1), CHART_COLORS.indigo, true);
}

function renderKpiRow(data, idx) {
  const prof = data.active_profiles[idx];
  const profPrev = idx > 0 ? data.active_profiles[idx - 1] : null;
  document.getElementById("active-profiles-value").textContent = fmtInt(prof);
  setPill(document.getElementById("active-profiles-delta"), pctChange(prof, profPrev));
  sparkline("profilesSparkline", data.active_profiles.slice(0, idx + 1), CHART_COLORS.sage);

  const recipients = data.campaigns.recipients[idx];
  document.getElementById("campaigns-count").textContent = recipients ? fmtInt(recipients) : "—";
  document.getElementById("campaigns-period").textContent = data.months[idx];

  const totalRevenue = (data.campaigns.revenue[idx] || 0) + (data.flows.revenue[idx] || 0);
  document.getElementById("total-revenue-value").textContent = fmtUSD(totalRevenue);
  const campShare = data.campaigns.share_of_total_revenue_pct[idx];
  const flowShare = data.flows.share_of_total_revenue_pct[idx];
  document.getElementById("revenue-share-sub").textContent = `Campaigns ${fmtPct(campShare, 0)} · Flows ${fmtPct(flowShare, 0)}`;
}

function renderLedger(tableId, block, idx) {
  const rows = [
    ["Open Rate", fmtPct(block.open_rate_pct[idx], 1)],
    ["CTR", fmtPct(block.ctr_pct[idx], 2)],
    ["Conversion Rate", fmtPct(block.conversion_rate_pct[idx], 2)],
    ["Revenue", fmtUSD(block.revenue[idx])],
    ["AOV", fmtUSD(block.aov[idx])],
    ["USD per customer", fmtUSD2(block.avg_usd_per_customer[idx])],
    ["Recipients", fmtInt(block.recipients[idx])],
    ["Unique Opens", fmtInt(block.unique_opens[idx])],
    ["Share of total revenue", fmtPct(block.share_of_total_revenue_pct[idx], 0)],
  ];
  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = rows.map(([label, value]) => `<tr><td>${label}</td><td>${value}</td></tr>`).join("");
}

function renderEvolution(data, metricPath, rangeMode, idx) {
  let months = data.months;
  let series = getByPath(data, metricPath);

  if (rangeMode === "quarter") {
    const [start, end] = quarterIndices(idx);
    months = months.slice(start, end + 1);
    series = series.slice(start, end + 1);
  } else {
    months = months.slice(0, idx + 1);
    series = series.slice(0, idx + 1);
  }
  lineChart("evolutionChart", months, series, CHART_COLORS.indigo, true);
}

function renderAll(data, state) {
  const idx = Number(state.monthIdx);
  renderHero(data, idx);
  renderKpiRow(data, idx);
  renderLedger("campaigns-table", data.campaigns, idx);
  renderLedger("flows-table", data.flows, idx);
  const activeMetricBtn = document.querySelector("#metric-toggle button.is-active");
  renderEvolution(data, activeMetricBtn.dataset.metric, state.range, idx);
}

async function init() {
  try {
    initTheme();
    const data = await loadData();
    const state = { monthIdx: data.months.length - 1, range: "month" };

    const monthSelect = populateMonthSelect(data);
    monthSelect.addEventListener("change", (e) => {
      state.monthIdx = e.target.value;
      renderAll(data, state);
    });

    document.querySelectorAll("#period-toggle button").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.dataset.range === "week") return; // weekly data not available yet
        document.querySelectorAll("#period-toggle button").forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        state.range = btn.dataset.range;
        renderAll(data, state);
      });
    });

    document.querySelectorAll("#metric-toggle button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#metric-toggle button").forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        renderAll(data, state);
      });
    });

    window.__redrawCharts = () => renderAll(data, state);

    renderAll(data, state);
  } catch (err) {
    document.querySelector(".wrap").innerHTML = `<p style="color:#E24C3D">Error loading data: ${err.message}</p>`;
    console.error(err);
  }
}

init();
