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
const fmtPct = (n, digits = 1) => n === null || n === undefined ? "—" : n.toFixed(digits) + "%";
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
  el.textContent = arrow + " " + Math.abs(value).toFixed(digits) + "%" + suffix;
  el.className = "pill " + (value >= 0 ? "" : "is-negative");
}

function setUnavailablePill(el, label = "N/A · no 2025 data") {
  el.textContent = label;
  el.className = "pill is-neutral";
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
function populateMonthSelect(months, defaultIdx) {
  const select = document.getElementById("month-select");
  select.innerHTML = months.map((m, i) => "<option value=\"" + i + "\">" + m + "</option>").join("");
  select.value = defaultIdx;
  return select;
}

function quarterIndices(monthIdx) {
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

function sumYTD(arr, maxIdx) {
  let sum = 0;
  for (let i = 0; i <= maxIdx; i++) {
    if (arr[i] !== null && arr[i] !== undefined) sum += arr[i];
  }
  return sum;
}

function renderHero(buData, meta, idx, compareMode) {
  const currYTD = sumYTD(buData.gross_sales, idx);
  const priorYTD = buData.gross_sales_2025 ? sumYTD(buData.gross_sales_2025.values, idx) : null;
  
  document.getElementById("hero-gross-sales-ytd").textContent = fmtUSD(currYTD);
  setPill(document.getElementById("hero-delta-ytd"), pctChange(currYTD, priorYTD), { suffix: " YoY" });

  const currMonth = buData.gross_sales[idx];
  document.getElementById("hero-gross-sales-month").textContent = fmtUSD(currMonth);

  if (compareMode === "yoy") {
    const priorMonth = buData.gross_sales_2025 ? buData.gross_sales_2025.values[idx] : null;
    setPill(document.getElementById("hero-delta-month"), pctChange(currMonth, priorMonth), { suffix: " YoY" });
  } else {
    const prevMonth = idx > 0 ? buData.gross_sales[idx - 1] : (buData.gross_sales_2025 ? buData.gross_sales_2025.values[11] : null);
    setPill(document.getElementById("hero-delta-month"), pctChange(currMonth, prevMonth));
  }

  document.getElementById("last-updated").textContent = meta.last_updated;
  document.getElementById("footer-note").textContent = meta.note;
}

function renderKpiRow(buData, idx, compareMode) {
  const prof = buData.active_profiles[idx];
  const profPrev = idx > 0 ? buData.active_profiles[idx - 1] : null;
  document.getElementById("active-profiles-value").textContent = fmtInt(prof);
  if (compareMode === "yoy") {
    setUnavailablePill(document.getElementById("active-profiles-delta"));
  } else {
    setPill(document.getElementById("active-profiles-delta"), pctChange(prof, profPrev));
  }

  const campYTD = sumYTD(buData.campaigns.revenue, idx);
  const flowYTD = sumYTD(buData.flows.revenue, idx);
  const totalYTD = campYTD + flowYTD;

  document.getElementById("kpi-campaigns-revenue").textContent = fmtUSD(campYTD);
  document.getElementById("kpi-campaigns-share").textContent = totalYTD > 0 ? fmtPct((campYTD / totalYTD) * 100, 1) + " of total revenue" : "—";

  document.getElementById("kpi-flows-revenue").textContent = fmtUSD(flowYTD);
  document.getElementById("kpi-flows-share").textContent = totalYTD > 0 ? fmtPct((flowYTD / totalYTD) * 100, 1) + " of total revenue" : "—";
}

function getVal(arr, idx) {
  if (idx < 0 || idx >= arr.length) return null;
  return arr[idx];
}

function renderLedger(tableId, block, months, idx) {
  const idx0 = idx;
  const idx1 = idx - 1;
  const idx2 = idx - 2;

  const thHtml = "<th></th><th style=\"text-align:right; font-weight:normal; color:var(--muted); font-size:12px; padding-bottom:4px;\">" + (idx2 >= 0 ? months[idx2] : '') + "</th><th style=\"text-align:right; font-weight:normal; color:var(--muted); font-size:12px; padding-bottom:4px;\">" + (idx1 >= 0 ? months[idx1] : '') + "</th><th style=\"text-align:right; font-weight:600; color:var(--ink); font-size:12px; padding-bottom:4px;\">" + months[idx0] + "</th>";
  document.querySelector("#" + tableId + " thead tr").innerHTML = thHtml;

  const rows = [
    { label: "Open Rate", fmt: (v) => fmtPct(v, 1), key: "open_rate_pct" },
    { label: "CTR", fmt: (v) => fmtPct(v, 2), key: "ctr_pct" },
    { label: "Conversion Rate", fmt: (v) => fmtPct(v, 2), key: "conversion_rate_pct" },
    { label: "Revenue", fmt: (v) => fmtUSD(v), key: "revenue" },
    { label: "AOV", fmt: (v) => fmtUSD(v), key: "aov" },
    { label: "USD per customer", fmt: (v) => fmtUSD2(v), key: "avg_usd_per_customer" },
    { label: "Unique Recipients", fmt: (v) => fmtInt(v), key: "recipients" },
    { label: "Unique Opens", fmt: (v) => fmtInt(v), key: "unique_opens" },
    { label: "Share of total revenue", fmt: (v) => fmtPct(v, 0), key: "share_of_total_revenue_pct" },
  ];

  const tbody = document.querySelector("#" + tableId + " tbody");
  tbody.innerHTML = rows.map(r => {
    const v2 = idx2 >= 0 ? r.fmt(getVal(block[r.key], idx2)) : '';
    const v1 = idx1 >= 0 ? r.fmt(getVal(block[r.key], idx1)) : '';
    const v0 = r.fmt(getVal(block[r.key], idx0));
    return "<tr><td>" + r.label + "</td><td style=\"text-align:right; font-variant-numeric: tabular-nums; color:var(--muted);\">" + v2 + "</td><td style=\"text-align:right; font-variant-numeric: tabular-nums; color:var(--muted);\">" + v1 + "</td><td>" + v0 + "</td></tr>";
  }).join("");
}

function renderEvolution(buData, months, metricPath, rangeMode, idx) {
  let m = months;
  let series = getByPath(buData, metricPath);

  if (rangeMode === "quarter") {
    const [start, end] = quarterIndices(idx);
    m = m.slice(start, end + 1);
    series = series.slice(start, end + 1);
  } else {
    m = m.slice(0, idx + 1);
    series = series.slice(0, idx + 1);
  }
  lineChart("evolutionChart", m, series, CHART_COLORS.indigo, true);
}

function renderAll(data, state) {
  const buData = data.bu_data[state.bu];
  const idx = Number(state.monthIdx);
  
  renderHero(buData, data.meta, idx, state.compare);
  renderKpiRow(buData, idx, state.compare);
  renderLedger("campaigns-table", buData.campaigns, data.months, idx);
  renderLedger("flows-table", buData.flows, data.months, idx);
  
  const activeMetricBtn = document.querySelector("#metric-toggle button.is-active");
  renderEvolution(buData, data.months, activeMetricBtn.dataset.metric, state.range, idx);
}

async function init() {
  try {
    initTheme();
    const data = await loadData();
    
    // Determine default BU
    const buSelect = document.getElementById("bu-select");
    const bu = buSelect ? buSelect.value : "CORRO";
    const defaultBuData = data.bu_data[bu];
    
    // Find last index with actual data
    let defaultIdx = data.months.length - 1;
    for (let i = data.months.length - 1; i >= 0; i--) {
      if (defaultBuData.gross_sales[i] !== null) {
        defaultIdx = i;
        break;
      }
    }
    
    const state = { bu, monthIdx: defaultIdx, range: "month", compare: "mom" };

    if (buSelect) {
      buSelect.addEventListener("change", (e) => {
        state.bu = e.target.value;
        renderAll(data, state);
      });
    }

    const monthSelect = populateMonthSelect(data.months, state.monthIdx);
    monthSelect.addEventListener("change", (e) => {
      state.monthIdx = e.target.value;
      renderAll(data, state);
    });

    document.getElementById("compare-select").addEventListener("change", (e) => {
      state.compare = e.target.value;
      renderAll(data, state);
    });

    document.querySelectorAll("#period-toggle button").forEach((btn) => {
      btn.addEventListener("click", () => {
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
    document.querySelector(".wrap").innerHTML = "<p style=\"color:#E24C3D\">Error loading data: " + err.message + "</p>";
    console.error(err);
  }
}

init();
