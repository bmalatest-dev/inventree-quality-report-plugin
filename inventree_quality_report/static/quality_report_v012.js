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
  const snapshotTotal = Number(report.snapshot?.total ?? 0);
  const snapRows = (report.snapshot?.rows || []).map(r => [
    r.status,
    String(r.count),
    snapshotTotal ? `${((Number(r.count) / snapshotTotal) * 100).toFixed(1)}%` : "—"
  ]);
  snapRows.push(["Total", String(snapshotTotal), snapshotTotal ? "100.0%" : "—"]);
  snap.appendChild(makeTable(["Current Status", "#", "%"], snapRows)); container.appendChild(snap);

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
    ["Status / Tracking Only", String(rw.status_only ?? 0), "—"],
    ["Rework Test Only", String(rw.test_only ?? 0), "—"],
    ["Found in Both", String(rw.both ?? 0), "—"],
    ["Current Rework Status", String(rw.current_status_detected ?? 0), "—"],
    ["Historical Rework Tracking", String(rw.tracking_history_detected ?? 0), "—"],
    ["Unique Stock Items Reworked", String(rw.unique_reworked ?? 0), fmtPercent(rw.rate_percentage)],
    ["Total Stock Items", String(rw.stock_items_evaluated ?? 0), rw.stock_items_evaluated ? "100.0%" : "—"]
  ]));
  container.appendChild(rework);
}

function csvEscape(value) {
  const text = value == null ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function downloadCsv(report) {
  const lines = [];
  const addRow = (...values) => lines.push(values.map(csvEscape).join(","));

  addRow("Part Quality Report");
  addRow("Part", report.part?.name || "");
  addRow("IPN", report.part?.ipn || "");
  addRow("Part ID", report.part?.pk ?? "");
  addRow("Stock Items Evaluated", report.stock_item_count ?? 0);
  addRow("");

  addRow("CURRENT STOCK SNAPSHOT");
  addRow("Current Status", "Count", "Percent");
  const snapshotTotalCsv = Number(report.snapshot?.total ?? 0);
  for (const row of report.snapshot?.rows || []) {
    addRow(
      row.status,
      row.count,
      snapshotTotalCsv ? ((Number(row.count) / snapshotTotalCsv) * 100).toFixed(1) : ""
    );
  }
  addRow("Total", snapshotTotalCsv, snapshotTotalCsv ? "100.0" : "");
  addRow("");

  addRow("FIRST PASS YIELD");
  addRow("FPY Test", "First Pass #", "Tested #", "FPY %");
  for (const row of report.fpy || []) {
    addRow(row.test, row.first_pass, row.tested, row.percentage == null ? "" : Number(row.percentage).toFixed(1));
  }
  addRow("");

  addRow("TEST DURATION");
  addRow("Test", "Timed Results", "Excluded", "Average Seconds", "Min Seconds", "Max Seconds");
  for (const row of report.timing || []) {
    addRow(row.test, row.timed_results, row.excluded, row.average_seconds ?? "", row.min_seconds ?? "", row.max_seconds ?? "");
  }
  addRow("");

  const rw = report.rework || {};
  addRow("REWORK RATE");
  addRow("Rework Metric", "Count", "Percent");
  addRow("Status / Tracking Only", rw.status_only ?? 0, "");
  addRow("Rework Test Only", rw.test_only ?? 0, "");
  addRow("Found in Both", rw.both ?? 0, "");
  addRow("Current Rework Status", rw.current_status_detected ?? 0, "");
  addRow("Historical Rework Tracking", rw.tracking_history_detected ?? 0, "");
  addRow("Unique Stock Items Reworked", rw.unique_reworked ?? 0, rw.rate_percentage == null ? "" : Number(rw.rate_percentage).toFixed(1));
  addRow("Total Stock Items", rw.stock_items_evaluated ?? 0, rw.stock_items_evaluated ? "100.0" : "");

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const base = (report.part?.ipn || report.part?.name || `part-${report.part?.pk || ""}`).replace(/[^a-z0-9_-]+/gi, "_");
  a.href = url;
  a.download = `${base}-quality-report.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function printReport(report, reportBox) {
  const popup = window.open("", "_blank");
  if (!popup) {
    window.alert("The print window was blocked by the browser. Allow pop-ups and try again.");
    return;
  }

  const partTitle = report.part?.ipn
    ? `${report.part.name} (${report.part.ipn})`
    : (report.part?.name || "Part");

  popup.document.open();
  popup.document.write(`
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <title>Part Quality Report - ${partTitle.replaceAll("<", "&lt;").replaceAll(">", "&gt;")}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 28px; color: #111; }
          h1 { margin: 0 0 4px; font-size: 22px; }
          .meta { margin-bottom: 18px; color: #555; font-size: 12px; }
          table { width: 100%; border-collapse: collapse; font-size: 12px; }
          th, td { padding: 6px 8px; border-bottom: 1px solid #ddd; }
          th:first-child, td:first-child { text-align: left !important; }
          th:not(:first-child), td:not(:first-child) { text-align: right !important; }
          @media print { body { margin: 12mm; } }
        </style>
      </head>
      <body>
        <h1>Part Quality Report</h1>
        <div class="meta">
          ${partTitle.replaceAll("<", "&lt;").replaceAll(">", "&gt;")} •
          Part ID ${report.part?.pk ?? ""} •
          ${report.stock_item_count ?? 0} stock item(s) evaluated
        </div>
        ${reportBox.innerHTML}
      </body>
    </html>
  `);
  popup.document.close();
  popup.focus();
  setTimeout(() => popup.print(), 250);
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

  let currentReport = null;

  const root = el("div", { style: { display: "flex", flexDirection: "column", gap: "8px", maxWidth: "1100px" } });
  const header = el("div", { style: { display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "center", flexWrap: "wrap" } });

  const tw = el("div");
  tw.appendChild(el("div", { text: partIpn ? `${partName} (${partIpn})` : partName, style: { fontWeight: "700", fontSize: "1.05rem" } }));
  tw.appendChild(el("div", { text: `Part ID ${partId} • report calculated on demand`, style: { opacity: "0.7", fontSize: "0.85rem" } }));

  const buttons = el("div", { style: { display: "flex", gap: "8px", flexWrap: "wrap" } });
  const refresh = el("button", { type: "button", text: "Refresh Report", style: { padding: "7px 12px", cursor: "pointer", borderRadius: "5px", border: "1px solid #868e96" } });
  const print = el("button", { type: "button", text: "Print / Save PDF", style: { padding: "7px 12px", cursor: "pointer", borderRadius: "5px", border: "1px solid #868e96" } });
  const csv = el("button", { type: "button", text: "Download CSV", style: { padding: "7px 12px", cursor: "pointer", borderRadius: "5px", border: "1px solid #868e96" } });

  print.disabled = true;
  csv.disabled = true;

  buttons.appendChild(refresh);
  buttons.appendChild(print);
  buttons.appendChild(csv);
  header.appendChild(tw);
  header.appendChild(buttons);
  root.appendChild(header);

  const status = el("div", { style: { minHeight: "20px", fontSize: "0.9rem" } });
  root.appendChild(status);

  const reportBox = el("div");
  root.appendChild(reportBox);
  target.appendChild(root);

  async function run() {
    refresh.disabled = true;
    print.disabled = true;
    csv.disabled = true;
    status.textContent = "Calculating quality report...";
    status.style.color = "";
    clear(reportBox);

    try {
      const report = await loadReport(api, partId);
      currentReport = report;
      renderReport(reportBox, report);
      print.disabled = false;
      csv.disabled = false;
      status.textContent = `Report ready. ${report.stock_item_count ?? 0} stock item(s) evaluated.`;
    } catch (error) {
      currentReport = null;
      status.textContent = `Quality report failed: ${errText(error)}`;
      status.style.color = "#e03131";
    } finally {
      refresh.disabled = false;
    }
  }

  refresh.addEventListener("click", run);
  print.addEventListener("click", () => currentReport && printReport(currentReport, reportBox));
  csv.addEventListener("click", () => currentReport && downloadCsv(currentReport));

  run();
}
