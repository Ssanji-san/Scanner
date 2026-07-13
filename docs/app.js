"use strict";

const CONDITION_LABELS = {
  c1: "Price above 150 & 200-day MA",
  c2: "150-day MA above 200-day MA",
  c3: "200-day MA rising (1 month+)",
  c4: "50-day MA above 150 & 200-day",
  c5: "Price above 50-day MA",
  c6: "≥30% above 52-week low",
  c7: "Within 25% of 52-week high",
  c8: "RS rating ≥ 70",
  c9: "Volume ≥ 20-day average",
};
const ZONE_LABELS = { low_cheat: "Low Cheat", mid_cheat: "Mid Cheat", cheat: "Cheat" };

let report = null;
let activeTab = "matches";
let sortState = {};

const $ = (sel) => document.querySelector(sel);

const fmt = {
  price: (v) => v == null ? "—" : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  pct: (v, signed = true) => {
    if (v == null) return "—";
    const pct = v * 100;
    const cls = pct >= 0 ? "pos" : "neg";
    return `<span class="${cls}">${signed && pct > 0 ? "+" : ""}${pct.toFixed(1)}%</span>`;
  },
  vol: (v) => {
    if (v == null) return "—";
    if (v >= 1e9) return (v / 1e9).toFixed(2) + "B";
    if (v >= 1e6) return (v / 1e6).toFixed(2) + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(0) + "K";
    return String(Math.round(v));
  },
  rs: (v) => {
    if (v == null) return "—";
    const cls = v >= 90 ? "rs-high" : v >= 70 ? "rs-mid" : "";
    return `<span class="${cls}">${v}</span>`;
  },
};

function sparkSvg(entry, { width = 120, height = 34, cup = false } = {}) {
  const points = entry.spark || [];
  if (points.length < 2) return "";
  const closes = points.map((p) => p[1]);
  let lo = Math.min(...closes), hi = Math.max(...closes);
  if (cup && entry.cup) hi = Math.max(hi, entry.cup.pivot);
  if (hi === lo) hi = lo + 1;
  const x = (i) => (i / (points.length - 1)) * width;
  const y = (v) => height - 3 - ((v - lo) / (hi - lo)) * (height - 6);
  const poly = points.map((p, i) => `${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");

  let extras = "";
  if (cup && entry.cup) {
    const dates = points.map((p) => p[0]);
    const idxAfter = (d) => {
      const i = dates.findIndex((dd) => dd >= d);
      return i === -1 ? dates.length - 1 : i;
    };
    const p1 = x(idxAfter(entry.cup.plateau_start));
    const p2 = x(idxAfter(entry.cup.plateau_end));
    const py = y(entry.cup.pivot);
    extras =
      `<rect class="plateau" x="${p1.toFixed(1)}" y="0" width="${Math.max(p2 - p1, 2).toFixed(1)}" height="${height}"></rect>` +
      `<line class="pivotline" x1="0" x2="${width}" y1="${py.toFixed(1)}" y2="${py.toFixed(1)}"></line>`;
  }
  return `<svg class="spark" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${extras}<polyline points="${poly}"></polyline></svg>`;
}

function tvLink(sym) {
  return `<a href="https://www.tradingview.com/chart/?symbol=${encodeURIComponent(sym)}" target="_blank" rel="noopener">${sym}</a>`;
}

function cupBadges(entry) {
  if (!entry.cup) return "";
  const zone = `<span class="badge zone-${entry.cup.zone}">${ZONE_LABELS[entry.cup.zone]}</span>`;
  const state = entry.cup.state === "triggered"
    ? `<span class="badge triggered">BREAKOUT</span>`
    : `<span class="badge forming">forming</span>`;
  return `${zone} ${state}`;
}

function detailRow(entry, cols) {
  const checks = Object.entries(CONDITION_LABELS).map(([key, label]) =>
    `<div class="${entry.conditions[key] ? "ok" : "fail"}">${key.toUpperCase()} — ${label}</div>`
  ).join("");
  let cup = "";
  if (entry.cup) {
    const c = entry.cup;
    cup = `<div class="cupinfo">Cup: <b>${ZONE_LABELS[c.zone]}</b> (${c.state}) ·
      pivot <b>$${fmt.price(c.pivot)}</b> · depth <b>${(c.depth * 100).toFixed(0)}%</b> ·
      confidence <b>${Math.round(c.confidence * 100)}%</b> ·
      lip ${c.lip_date} $${fmt.price(c.lip_price)} → low ${c.low_date} $${fmt.price(c.low_price)} ·
      pause ${c.plateau_start} → ${c.plateau_end}</div>`;
  }
  const pref = entry.metrics.ma200_trend_preferred
    ? `<div class="cupinfo">★ 200-day MA rising 5+ months (Minervini's preferred)</div>` : "";
  return `<tr class="detail hidden"><td colspan="${cols}"><div class="checklist">${checks}</div>${cup}${pref}</td></tr>`;
}

const COLUMNS = {
  standard: [
    { key: "symbol", label: "Symbol", left: true, val: (e) => e.symbol },
    { key: "price", label: "Price", val: (e) => e.price },
    { key: "rs", label: "RS", val: (e) => e.rs ?? -1 },
    { key: "above_low", label: "vs 52w Low", val: (e) => e.metrics.pct_above_low },
    { key: "from_high", label: "vs 52w High", val: (e) => e.metrics.pct_from_high },
    { key: "volume", label: "Volume", val: (e) => e.metrics.volume },
    { key: "relvol", label: "RelVol", val: (e) => e.metrics.volume / (e.metrics.vol_ema || 1) },
    { key: "days", label: "Days", val: (e) => e.days_on_list ?? 0 },
    { key: "tmpl", label: "Template", val: (e) => 9 - e.failed.length },
    { key: "badges", label: "", val: () => 0 },
    { key: "spark", label: "1Y", val: () => 0 },
  ],
  cups: [
    { key: "symbol", label: "Symbol", left: true, val: (e) => e.symbol },
    { key: "price", label: "Price", val: (e) => e.price },
    { key: "rs", label: "RS", val: (e) => e.rs ?? -1 },
    { key: "zone", label: "Entry Zone", val: (e) => e.cup.zone },
    { key: "state", label: "State", val: (e) => e.cup.state },
    { key: "pivot", label: "Pivot", val: (e) => e.cup.pivot },
    { key: "depth", label: "Depth", val: (e) => e.cup.depth },
    { key: "conf", label: "Confidence", val: (e) => e.cup.confidence },
    { key: "tmpl", label: "Template", val: (e) => 9 - e.failed.length },
    { key: "spark", label: "1Y", val: () => 0 },
  ],
};

function cellHtml(col, entry, isCupTab) {
  switch (col.key) {
    case "symbol":
      return `<td class="sym left">${tvLink(entry.symbol)}${entry.is_new ? ' <span class="badge new">NEW</span>' : ""}<br><span class="name">${entry.name}</span></td>`;
    case "price": return `<td>$${fmt.price(entry.price)}</td>`;
    case "rs": return `<td>${fmt.rs(entry.rs)}</td>`;
    case "above_low": return `<td>${fmt.pct(entry.metrics.pct_above_low)}</td>`;
    case "from_high": return `<td>${fmt.pct(entry.metrics.pct_from_high)}</td>`;
    case "volume": return `<td>${fmt.vol(entry.metrics.volume)}</td>`;
    case "relvol": {
      const rv = entry.metrics.volume / (entry.metrics.vol_ema || 1);
      return `<td class="${rv >= 1.5 ? "pos" : ""}">${rv.toFixed(2)}</td>`;
    }
    case "days": return `<td>${entry.days_on_list ?? "—"}</td>`;
    case "badges": return `<td>${cupBadges(entry)}</td>`;
    case "spark": return `<td>${sparkSvg(entry, { cup: !!entry.cup && isCupTab, width: isCupTab ? 220 : 120, height: isCupTab ? 48 : 34 })}</td>`;
    case "zone": return `<td><span class="badge zone-${entry.cup.zone}">${ZONE_LABELS[entry.cup.zone]}</span></td>`;
    case "state": return `<td>${entry.cup.state === "triggered" ? '<span class="badge triggered">BREAKOUT</span>' : '<span class="badge forming">forming</span>'}</td>`;
    case "pivot": return `<td>$${fmt.price(entry.cup.pivot)}</td>`;
    case "depth": return `<td>${(entry.cup.depth * 100).toFixed(0)}%</td>`;
    case "conf": return `<td>${Math.round(entry.cup.confidence * 100)}%</td>`;
    case "tmpl": {
      const passed = 9 - entry.failed.length;
      const misses = entry.failed.length
        ? ` <span class="neg" title="${entry.failed.map((k) => CONDITION_LABELS[k]).join(" · ")}">✗ ${entry.failed.map((k) => k.toUpperCase()).join(",")}</span>`
        : "";
      return `<td><span class="${passed === 9 ? "pos" : ""}">${passed}/9</span>${misses}</td>`;
    }
    default: return "<td></td>";
  }
}

function renderTable(panelId, entries, colSet, isCupTab = false) {
  const panel = $(panelId);
  const query = $("#search").value.trim().toLowerCase();
  let rows = entries;
  if (query) {
    rows = rows.filter((e) =>
      e.symbol.toLowerCase().includes(query) || (e.name || "").toLowerCase().includes(query));
  }
  if (priceFilter.min != null) rows = rows.filter((e) => e.price >= priceFilter.min);
  if (priceFilter.max != null) rows = rows.filter((e) => e.price <= priceFilter.max);
  const sort = sortState[panelId];
  if (sort) {
    const col = colSet.find((c) => c.key === sort.key);
    if (col) {
      rows = [...rows].sort((a, b) => {
        const av = col.val(a), bv = col.val(b);
        const cmp = typeof av === "string" ? av.localeCompare(bv) : av - bv;
        return sort.dir === "asc" ? cmp : -cmp;
      });
    }
  }
  if (!rows.length) {
    panel.innerHTML = `<div class="empty">${query ? "Nothing matches your filter." : "Nothing here in this scan."}</div>`;
    return;
  }
  const head = colSet.map((c) =>
    `<th class="${c.left ? "left" : ""}" data-key="${c.key}">${c.label}${sort && sort.key === c.key ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}</th>`).join("");
  const body = rows.map((e) => {
    const cells = colSet.map((c) => cellHtml(c, e, isCupTab)).join("");
    return `<tr class="datarow">${cells}</tr>${detailRow(e, colSet.length)}`;
  }).join("");
  panel.innerHTML = `<div class="tablewrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;

  panel.querySelectorAll("thead th").forEach((th) => th.addEventListener("click", () => {
    const key = th.dataset.key;
    const cur = sortState[panelId];
    sortState[panelId] = { key, dir: cur && cur.key === key && cur.dir === "desc" ? "asc" : "desc" };
    render();
  }));
  panel.querySelectorAll("tr.datarow").forEach((tr) => tr.addEventListener("click", (ev) => {
    if (ev.target.closest("a")) return;
    tr.nextElementSibling.classList.toggle("hidden");
  }));
}

function render() {
  renderTable("#panel-matches", report.matches, COLUMNS.standard);
  renderTable("#panel-near", report.near_misses, COLUMNS.standard);
  renderTable("#panel-cups", report.cups || [], COLUMNS.cups, true);
}

function setTab(tab) {
  activeTab = tab;
  document.querySelectorAll("nav#tabs button").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === tab));
  ["matches", "near", "cups"].forEach((t) =>
    $(`#panel-${t}`).classList.toggle("hidden", t !== tab));
}

async function init() {
  let data;
  try {
    const resp = await fetch("data/latest.json", { cache: "no-store" });
    data = await resp.json();
  } catch (err) {
    document.querySelector("main").innerHTML =
      `<div class="empty">Could not load data/latest.json — run a scan first.<br>${err}</div>`;
    return;
  }
  report = data;
  $("#scan-date").innerHTML = `Scan date: <b>${report.scan_date}</b>`;
  $("#universe").innerHTML = `Universe scanned: <b>${report.universe_size.toLocaleString()}</b>`;
  const newTxt = report.new.length ? `NEW: <b class="pos">${report.new.join(", ")}</b>` : "no new matches";
  const dropTxt = report.dropped.length ? `dropped: <span class="neg">${report.dropped.join(", ")}</span>` : "";
  $("#diff").innerHTML = `${newTxt} ${dropTxt}`;
  $("#count-matches").textContent = `(${report.matches.length})`;
  $("#count-near").textContent = `(${report.near_misses.length})`;
  $("#count-cups").textContent = `(${(report.cups || []).length})`;
  if (report.demo) $("#demo-badge").classList.remove("hidden");
  $("#footer-note").textContent =
    "Data: Alpaca (IEX feed) · Float-free scan — conditions use price, volume and MAs only · Click a row for the condition checklist.";
  render();
}

document.querySelectorAll("nav#tabs button").forEach((b) =>
  b.addEventListener("click", () => setTab(b.dataset.tab)));
$("#search").addEventListener("input", render);

const priceFilter = { min: null, max: null };

function applyPriceFilter() {
  const min = parseFloat($("#price-min").value);
  const max = parseFloat($("#price-max").value);
  priceFilter.min = Number.isNaN(min) ? null : min;
  priceFilter.max = Number.isNaN(max) ? null : max;
  $("#price-pop").classList.add("hidden");

  const chip = $("#price-chip");
  if (priceFilter.min == null && priceFilter.max == null) {
    chip.classList.add("hidden");
  } else {
    let text;
    if (priceFilter.min != null && priceFilter.max != null) text = `Price ${priceFilter.min} – ${priceFilter.max} USD`;
    else if (priceFilter.min != null) text = `Price > ${priceFilter.min} USD`;
    else text = `Price < ${priceFilter.max} USD`;
    $("#price-chip-text").textContent = text;
    chip.classList.remove("hidden");
  }
  render();
}

$("#price-btn").addEventListener("click", (ev) => {
  ev.stopPropagation();
  $("#price-pop").classList.toggle("hidden");
  if (!$("#price-pop").classList.contains("hidden")) $("#price-min").focus();
});
$("#price-apply").addEventListener("click", applyPriceFilter);
$("#price-pop").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") applyPriceFilter();
});
$("#price-pop").addEventListener("click", (ev) => ev.stopPropagation());
document.addEventListener("click", () => $("#price-pop").classList.add("hidden"));
$("#price-clear").addEventListener("click", () => {
  $("#price-min").value = "";
  $("#price-max").value = "";
  applyPriceFilter();
});

init();
