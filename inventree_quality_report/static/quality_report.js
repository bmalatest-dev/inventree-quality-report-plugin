function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.text !== undefined) node.textContent = options.text;
  if (options.type) node.type = options.type;
  if (options.style) Object.assign(node.style, options.style);
  for (const child of children) if (child) node.appendChild(child);
  return node;
}

function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function fmtPercent(value) { return value == null ? "—" : `${Number(value).toFixed(1)}%`; }
function fmtDuration(seconds) {
  if (seconds == null) return "—";
  const n = Math.round(Number(seconds));
  const h = Math.floor(n / 3600), m = Math.floor((n % 3600) / 60), s = n % 60;
  const parts = [];
  if (h) parts.push(`${h}h`);
  if (m || h) parts.push(`${m}m`);
  parts.push(`${s}s`);
  return parts.join(" ");
}

function makeTable(headers, rows) {
  const wrap = el("div", { style: { overflowX: "auto", width: "100%" } });
  const table = el("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: "0.92rem" } });
  const thead = el("thead"), trh = el("tr");
  headers.forEach((h, i) => trh.appendChild(el("th", { text: h, style: { textAlign: i === 0 ? "left" : "right", padding: "7px 8px", borderBottom: "1px solid #ced4da", whiteSpace: "nowrap" } })));
  thead.appendChild(trh); table.appendChild(thead);
  const tbody = el("tbody");
  rows.forEach((row, ri) => {
    const tr = el("tr");
    row.forEach((cell, ci) => tr.appendChild(el("td", { text: cell, style: { textAlign: ci === 0 ? "left" : "right", padding: "7px 8px", borderBottom: ri === rows.length - 1 ? "none" : "1px solid #e9ecef", whiteSpace: "nowrap" } })));
    tbody.appendChild(tr);
  });
  table.appendChild(tbody); wrap.appendChild(table); return wrap;
}

function section(title, subtitle = "") {
  const box = el("div", { style: { border: "1px solid #ced4da", borderRadius: "7px", padding: "12px", marginTop: "12px" } });
  box.appendChild(el("div", { text: title, style: { fontSize: "1rem", fontWeight: "700", marginBottom: "3px" } }));
  if (subtitle) box.appendChild(el("div", { text: subtitle, style: { fontSize: "0.85rem", opacity: "0.72", marginBottom: "9px" } }));
  return box;
}

function errText(error) {
  const data = error?.response?.data;
  if (typeof data === "string") return data;
  if (data) { try { return JSON.stringify(data); } catch (_) {} }
  return error?.message || "Unknown error";
}

async function loadReport(api, partId) {
  const response = await api.post("/api/action/", { action: "part_quality_report", data: { part: partId } });
  return response.data?.result || response.data;
}

function renderReport(container, report) {
  clear(container);

  const snap = section("Current Stock Snapshot", "Current status only; historical states do not affect this table.");
  const snapRows = (report.snapshot?.rows || []).map(r => [r.status, String(r.count)]);
  snapRows.push(["Total", String(report.snapshot?.total ?? 0)]);
  snap.appendChild(makeTable(["Current Status", "#"], snapRows)); container.appendChild(snap);

  const fpy = section("First Pass Yield", "A stock item passes FPY only when its first recorded attempt for that test passed.");
  const fpyRows = (report.fpy || []).map(r => [r.test, String(r.first_pass), String(r.tested), fmtPercent(r.percentage)]);
  fpy.appendChild(fpyRows.length ? makeTable(["FPY Test", "First Pass #", "Tested #", "FPY %"], fpyRows) : el("div", { text: "No test results found for this Part." }));
  container.appendChild(fpy);

  const timing = section("Test Duration", "Finished − Started. Missing, zero-duration, and negative-duration records are excluded.");
  const timingRows = (report.timing || []).map(r => [r.test, String(r.timed_results), String(r.excluded), fmtDuration(r.average_seconds), fmtDuration(r.min_seconds), fmtDuration(r.max_seconds)]);
  timing.appendChild(timingRows.length ? makeTable(["Test", "Timed Results", "Excluded", "Average", "Min", "Max"], timingRows) : el("div", { text: "No test templates or results found." }));
  container.appendChild(timing);

  const rw = report.rework || {};
  const rework = section("Rework Rate", "Hybrid detection: stock status history OR a recorded Rework test result. A stock item matching both is counted once.");
  rework.appendChild(makeTable(["Rework Metric", "#", "%"], [
    ["Stock Tracking Only", String(rw.tracking_only ?? 0), "—"],
    ["Rework Test Only", String(rw.test_only ?? 0), "—"],
    ["Found in Both", String(rw.both ?? 0), "—"],
    ["Unique Stock Items Reworked", String(rw.unique_reworked ?? 0), fmtPercent(rw.rate_percentage)],
    ["Total Stock Items", String(rw.stock_items_evaluated ?? 0), rw.stock_items_evaluated ? "100.0%" : "—"]
  ]));
  container.appendChild(rework);
}

export function renderQualityReportPanel(target, data) {
  clear(target);
  const api = data?.api;
  const partId = Number(data?.context?.part_id ?? data?.id);
  const partName = data?.context?.part_name || data?.instance?.name || `Part ${partId}`;
  const partIpn = data?.context?.part_ipn || data?.instance?.IPN || "";
  if (!api || !partId) {
    target.appendChild(el("div", { text: "Quality Report could not determine the current Part or API context." }));
    return;
  }

  const root = el("div", { style: { display: "flex", flexDirection: "column", gap: "8px", maxWidth: "1100px" } });
  const header = el("div", { style: { display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "center", flexWrap: "wrap" } });
  const tw = el("div");
  tw.appendChild(el("div", { text: partIpn ? `${partName} (${partIpn})` : partName, style: { fontWeight: "700", fontSize: "1.05rem" } }));
  tw.appendChild(el("div", { text: `Part ID ${partId} • report calculated on demand`, style: { opacity: "0.7", fontSize: "0.85rem" } }));
  const refresh = el("button", { type: "button", text: "Refresh Report", style: { padding: "7px 12px", cursor: "pointer", borderRadius: "5px", border: "1px solid #868e96" } });
  header.appendChild(tw); header.appendChild(refresh); root.appendChild(header);
  const status = el("div", { style: { minHeight: "20px", fontSize: "0.9rem" } }); root.appendChild(status);
  const reportBox = el("div"); root.appendChild(reportBox); target.appendChild(root);

  async function run() {
    refresh.disabled = true; status.textContent = "Calculating quality report..."; status.style.color = ""; clear(reportBox);
    try {
      const report = await loadReport(api, partId);
      renderReport(reportBox, report);
      status.textContent = `Report ready. ${report.stock_item_count ?? 0} stock item(s) evaluated.`;
    } catch (error) {
      status.textContent = `Quality report failed: ${errText(error)}`; status.style.color = "#e03131";
    } finally { refresh.disabled = false; }
  }
  refresh.addEventListener("click", run); run();
}
