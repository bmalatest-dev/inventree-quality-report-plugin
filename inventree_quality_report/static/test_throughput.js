const reportUrl = "/plugin/part-quality-report/throughput/";
const requestTimeout = 60000;
const columns = [
  ["units", "Units processed"],
  ["runs", "Runs"],
  ["hours", "Recorded hours"],
  ["timed_units", "Timed units"],
  ["units_per_hour", "Units/hour"],
  ["first_attempt_units", "First-attempt units"],
  ["retest_units", "Retest units"],
  ["untimed_runs", "Untimed runs"],
  ["legacy_runs", "Estimated runs"],
];
const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

function append(parent, tag, text) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  parent.appendChild(node);
  return node;
}

function setOptions(select, options, allLabel, selected = "") {
  select.replaceChildren(new Option(allLabel, ""));
  for (const [value, label] of options) select.add(new Option(label, value));
  if (selected && !Array.from(select.options).some(option => option.value === selected)) {
    select.add(new Option(selected, selected));
  }
  select.value = selected;
}

function groupBy(rows, key) {
  const groups = new Map();
  for (const row of rows) {
    const value = key(row);
    if (!groups.has(value)) groups.set(value, []);
    groups.get(value).push(row);
  }
  return groups;
}

function renderSummary(container, rows) {
  container.replaceChildren();
  if (!rows.length) {
    append(container, "p", "No matching test results.");
    return;
  }

  const table = append(container, "table");
  table.style.cssText = "border-collapse:collapse;width:100%;text-align:left";
  const heading = append(append(table, "thead"), "tr");
  for (const label of ["User / Part / Test / Work date", ...columns.map(([, label]) => label)]) {
    const header = append(heading, "th", label);
    header.scope = "col";
    header.style.padding = "0.5rem";
  }
  const body = append(table, "tbody");

  function addRow(row, label, depth, expandable) {
    const line = append(body, "tr");
    const name = append(line, "td");
    name.style.cssText = `padding:0.5rem; padding-left:${0.5 + depth}rem`;
    const control = append(name, expandable ? "button" : "span", label);
    if (expandable) control.type = "button";
    for (const [field] of columns) {
      const cell = append(line, "td", row[field] == null ? "—" : number.format(row[field]));
      cell.style.cssText = "padding:0.5rem;text-align:right;white-space:nowrap";
    }
    return { line, control };
  }

  const levels = [
    ["User total", row => row.user_id, row => row.user],
    ["Part total", row => row.part_id, row => row.revision ? `${row.part} (Rev ${row.revision})` : row.part],
    ["Part and test", row => row.test_key, row => row.test],
    ["Daily", row => row.date, row => row.date],
  ];

  function renderLevel(rows, depth) {
    const [level, key, label] = levels[depth];
    return Array.from(groupBy(rows, key).values(), group => {
      const row = group.find(item => item.level === level);
      const remaining = group.filter(item => item !== row);
      const { line, control } = addRow(row, label(row), depth, remaining.length > 0);
      line.hidden = depth > 0;
      const children = remaining.length ? renderLevel(remaining, depth + 1) : [];
      if (children.length) {
        control.setAttribute("aria-expanded", "false");
        control.addEventListener("click", () => {
          const expanded = control.getAttribute("aria-expanded") !== "true";
          control.setAttribute("aria-expanded", String(expanded));
          for (const child of children) child.setVisible(expanded);
        });
      }
      return {
        setVisible(visible) {
          line.hidden = !visible;
          for (const child of children) {
            child.setVisible(visible && control.getAttribute("aria-expanded") === "true");
          }
        },
      };
    });
  }

  renderLevel(rows, 0);
}

export function renderTestThroughput(target, { api }) {
  target.replaceChildren();
  append(target, "h2", "Test Throughput by User");
  append(target, "p", "Work dates use Toronto time and are based on test start, then finish or recording time if start is missing. Recorded hours sum elapsed test time, including overlapping runs. Older quantities are estimated from current stock.");
  const form = append(target, "form");
  form.style.cssText = "display:flex;flex-wrap:wrap;gap:0.75rem;align-items:end";

  function field(label, name, type) {
    const wrapper = append(form, "label", label);
    wrapper.style.cssText = "display:flex;flex-direction:column;gap:0.25rem";
    const input = append(wrapper, type === "select" ? "select" : "input");
    input.name = name;
    if (type !== "select") input.type = type;
    return input;
  }

  const start = field("From", "start", "date");
  const end = field("Through", "end", "date");
  const user = field("Recorded by", "user", "select");
  const part = field("Part", "part", "search");
  part.placeholder = "IPN, name, or ID";
  const test = field("Test", "test", "select");
  const outcome = field("Result", "outcome", "select");
  setOptions(user, [], "All users");
  setOptions(test, [], "All tests");
  setOptions(outcome, [["pass", "Pass"], ["fail", "Fail"]], "All results");

  const apply = append(form, "button", "Run report");
  apply.type = "submit";
  const download = append(form, "button", "Download CSV");
  download.type = "button";
  download.disabled = true;
  const status = append(target, "p");
  status.setAttribute("role", "status");
  const results = append(target, "div");
  results.style.overflowX = "auto";
  let appliedFilters;

  async function load() {
    apply.disabled = download.disabled = true;
    status.textContent = "Loading test results…";
    results.replaceChildren();
    const params = Object.fromEntries(new FormData(form));
    try {
      const { data } = await api.get(reportUrl + "data/", { params, timeout: requestTimeout });
      start.value = data.start;
      end.value = data.end;
      setOptions(user, data.users, "All users", params.user);
      setOptions(test, data.tests, "All tests", params.test);
      appliedFilters = { ...params, start: data.start, end: data.end };
      renderSummary(results, data.summary);
      status.textContent = params.test ? "" : "Select a single test to show units/hour in the user and part totals.";
      download.disabled = false;
    } catch (error) {
      status.textContent = error.response?.status === 403
        ? "InvenTree superuser access is required."
        : error.response?.data?.error || "Could not load test throughput.";
    } finally {
      apply.disabled = false;
    }
  }

  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!apply.disabled) load();
  });

  download.addEventListener("click", async () => {
    apply.disabled = download.disabled = true;
    status.textContent = "Preparing CSV…";
    try {
      const { data } = await api.get(reportUrl + "csv/", {
        params: appliedFilters,
        responseType: "blob",
        timeout: requestTimeout,
      });
      if (!data.type.startsWith("text/csv")) throw new Error("Expected a CSV file");
      const url = URL.createObjectURL(data);
      const link = document.createElement("a");
      link.href = url;
      link.download = "test-throughput-by-user.csv";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      status.textContent = "CSV downloaded.";
    } catch {
      status.textContent = "Could not download the CSV.";
    } finally {
      apply.disabled = download.disabled = false;
    }
  });

  load();
}
