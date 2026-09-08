const CHART_COLORS = {
  gold: "#C9A227",
  sage: "#7C9A82",
  clay: "#E4572E",
  grid: "rgba(246,242,233,0.08)",
  text: "rgba(246,242,233,0.6)"
};

const fmtUSD = (n) => n === null || n === undefined
  ? "—"
  : "$" + Math.round(n).toLocaleString("en-US");

const fmtInt = (n) => n === null || n === undefined ? "—" : Math.round(n).toLocaleString("en-US");

const fmtPct = (n, digits = 1) => n === null || n === undefined ? "—" : `${n.toFixed(digits)}%`;

const fmtUSD2 = (n) => n === null || n === undefined ? "—" : "$" + n.toFixed(2);

function deltaClass(value) {
  if (value === null || value === undefined) return "";
  return value >= 0 ? "is-positive" : "is-negative";
}

function lastAndPrev(arr) {
  const last = arr[arr.length - 1];
  const prev = arr[arr.length - 2];
  return { last, prev };
}

function pctChange(last, prev) {
  if (prev === null || prev === undefined || prev === 0 || last === null || last === undefined) return null;
  return ((last - prev) / Math.abs(prev)) * 100;
}

function getByPath(obj, path) {
  return path.split(".").reduce((acc, key) => (acc ? acc[key] : undefined), obj);
}

async function loadData() {
  const res = await fetch("data/data.json", { cache: "no-store" });
  if (!res.ok) throw new Error("No se pudo cargar data/data.json");
  return res.json();
}

function renderHero(data) {
  const { months, gross_sales } = data;
  const { last, prev } = lastAndPrev(gross_sales);
  document.getElementById("hero-gross-sales").textContent = fmtUSD(last);

  const change = pctChange(last, prev);
  const deltaEl = document.getElementById("hero-delta");
  if (change === null) {
    deltaEl.textContent = `${months[months.length - 1]}`;
  } else {
    deltaEl.textContent = `${change >= 0 ? "▲" : "▼"} ${Math.abs(change).toFixed(1)}% vs ${months[months.length - 2]} · ${months[months.length - 1]}`;
    deltaEl.classList.add(change >= 0 ? "is-positive" : "is-negative");
  }

  document.getElementById("last-updated").textContent = `actualizado ${data.meta.last_updated}`;
  document.getElementById("source-tag").textContent = "AC";
  document.getElementById("footer-note").textContent = data.meta.note;
}

function renderStatCards(data) {
  const { months, active_profiles, active_base_growth_pct, campaigns, flows } = data;
  const { last: profLast } = lastAndPrev(active_profiles);
  const growth = active_base_growth_pct[active_base_growth_pct.length - 1];

  document.getElementById("active-profiles-value").textContent = fmtInt(profLast);
  const profDeltaEl = document.getElementById("active-profiles-delta");
  profDeltaEl.textContent = growth === null ? "—" : `${growth >= 0 ? "▲" : "▼"} ${Math.abs(growth).toFixed(2)}% vs mes anterior`;
  profDeltaEl.classList.add(deltaClass(growth));

  // "Campañas enviadas" — the sheet doesn't track a raw campaign count, so we
  // surface recipients + period as the closest available proxy until that
  // field is connected.
  const lastRecipients = campaigns.recipients[campaigns.recipients.length - 1];
  document.getElementById("campaigns-count").textContent = lastRecipients ? fmtInt(lastRecipients) + " destinatarios" : "—";
  document.getElementById("campaigns-period").textContent = months[months.length - 1];

  const totalRevenue = campaigns.revenue[campaigns.revenue.length - 1] + flows.revenue[flows.revenue.length - 1];
  document.getElementById("total-revenue-value").textContent = fmtUSD(totalRevenue);
  const campShare = campaigns.share_of_total_revenue_pct[campaigns.share_of_total_revenue_pct.length - 1];
  const flowShare = flows.share_of_total_revenue_pct[flows.share_of_total_revenue_pct.length - 1];
  document.getElementById("revenue-share-sub").textContent = `Campaigns ${fmtPct(campShare, 0)} · Flows ${fmtPct(flowShare, 0)}`;
}

function renderLedger(tableId, block, target) {
  const idx = block.revenue.length - 1;
  const rows = [
    ["Open Rate", fmtPct(block.open_rate_pct[idx], 1), null],
    ["CTR", fmtPct(block.ctr_pct[idx], 2), null],
    ["Conversion Rate", fmtPct(block.conversion_rate_pct[idx], 2), null],
    ["Revenue generado", fmtUSD(block.revenue[idx]), null],
    ["AOV", fmtUSD(block.aov[idx]), null],
    ["Recipients", fmtInt(block.recipients[idx]), null],
    ["Unique Opens", fmtInt(block.unique_opens[idx]), null],
    ["% share of total revenue", fmtPct(block.share_of_total_revenue_pct[idx], 0), null],
  ];
  if (target.avg_usd_per_customer) rows.splice(4, 0, ["USD promedio / cliente", fmtUSD2(block.avg_usd_per_customer[idx]), null]);

  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = rows.map(([label, value]) => `<tr><td>${label}</td><td>${value}</td></tr>`).join("");
}

function lineChart(ctx, labels, series, color, fill = false) {
  return new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        data: series,
        borderColor: color,
        backgroundColor: fill ? color + "22" : "transparent",
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
        x: { grid: { display: false }, ticks: { color: CHART_COLORS.text, font: { size: 11 } } },
        y: { grid: { color: CHART_COLORS.grid }, ticks: { color: CHART_COLORS.text, font: { size: 11 } } },
      },
    },
  });
}

function sparkline(ctx, series, color) {
  return new Chart(ctx, {
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

let evolutionChart;
function renderEvolution(data, metricPath) {
  const ctx = document.getElementById("evolutionChart");
  const series = getByPath(data, metricPath);
  if (evolutionChart) evolutionChart.destroy();
  evolutionChart = lineChart(ctx, data.months, series, CHART_COLORS.gold, true);
}

function setupToggle(data) {
  const buttons = document.querySelectorAll("#metric-toggle button");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      renderEvolution(data, btn.dataset.metric);
    });
  });
}

async function init() {
  try {
    const data = await loadData();
    renderHero(data);
    renderStatCards(data);
    renderLedger("campaigns-table", data.campaigns, data.campaigns);
    renderLedger("flows-table", data.flows, data.flows);

    lineChart(document.getElementById("grossSalesChart"), data.months, data.gross_sales, CHART_COLORS.gold, true);
    sparkline(document.getElementById("profilesSparkline"), data.active_profiles, CHART_COLORS.sage);

    renderEvolution(data, "gross_sales");
    setupToggle(data);
  } catch (err) {
    document.querySelector(".wrap").innerHTML = `<p style="color:#E4572E">Error cargando datos: ${err.message}</p>`;
    console.error(err);
  }
}

init();
