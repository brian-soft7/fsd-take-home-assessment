"use strict";

/* ---------- Constants ---------- */

const FIELD_LABELS = {
  title: "Title",
  start: "Start",
  end: "End",
  type: "Type",
  status: "Status",
  loc: "Location",
  owner: "Owner",
  client: "Client",
  people: "Attendees",
  notes: "Notes",
};

const SOURCE_LABELS = { crm: "CRM", cal: "Calendar", both: "Both agree" };

// Field kinds that get a badge next to the value
const FLAGGED_KINDS = ["conflict", "diff", "filled"];

const ISO_DATETIME = /^\d{4}-\d\d-\d\dT/;

/* ---------- DOM references ---------- */

const dom = {
  stats: document.getElementById("stats"),
  meetings: document.getElementById("meetings"),
  report: document.getElementById("report"),
  search: document.getElementById("search"),
  source: document.getElementById("source"),
  conflictsOnly: document.getElementById("conflicts-only"),
  sync: document.getElementById("sync"),
};

/* ---------- Formatting helpers ---------- */

function escapeHtml(value) {
  const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };
  return String(value ?? "").replace(/[&<>"]/g, (ch) => entities[ch]);
}

// The API already returns New York time, so the string only needs trimming.
function formatTime(value) {
  if (!value) return "-";
  if (!value.includes("T")) return `${value} (no time)`;
  return `${value.slice(0, 10)} ${value.slice(11, 16)}`;
}

// Renders any field value as safe HTML.
function formatValue(value) {
  const isEmpty =
    value == null || value === "" || (Array.isArray(value) && value.length === 0);
  if (isEmpty) return '<span class="none">-</span>';
  if (Array.isArray(value)) return escapeHtml(value.join(", "));
  if (ISO_DATETIME.test(value)) return escapeHtml(formatTime(value));
  return escapeHtml(value);
}

function badge(kind, text) {
  return `<span class="badge badge-${kind}">${escapeHtml(text)}</span>`;
}

/* ---------- Rendering ---------- */

function renderStats(counts, duplicateCount) {
  const items = [
    ["meetings", counts.meetings],
    ["in both", counts.both],
    ["CRM only", counts.crm_only],
    ["Calendar only", counts.cal_only],
    ["with conflicts", counts.conflicts],
    ["duplicates merged", duplicateCount],
    ["data warnings", counts.warns],
  ];
  dom.stats.innerHTML = items
    .map(([label, n]) => `<li class="stat"><strong>${n}</strong> ${label}</li>`)
    .join("");
}

function renderFieldRow(name, field) {
  const flag = FLAGGED_KINDS.includes(field.kind) ? ` ${badge(field.kind, field.kind)}` : "";
  const source = field.src ? badge(field.src, SOURCE_LABELS[field.src]) : "";
  const reason = field.note ? `${field.rule} - ${field.note}` : field.rule;

  return `
    <tr class="field-${field.kind}">
      <th scope="row">${FIELD_LABELS[name]}</th>
      <td>${formatValue(field.crm)}</td>
      <td>${formatValue(field.cal)}</td>
      <td class="shown">${formatValue(field.show)}<span class="note">${escapeHtml(reason)}</span></td>
      <td>${source}${flag}</td>
    </tr>`;
}

function renderDetail(meeting) {
  const fieldRows = Object.entries(meeting.fields)
    .map(([name, field]) => renderFieldRow(name, field))
    .join("");

  const ids = `
    <p class="muted">
      CRM: ${escapeHtml(meeting.ids.crm ?? "none")} |
      Calendar: ${escapeHtml(meeting.ids.cal.join(", ") || "none")}
    </p>`;

  const match = meeting.match
    ? `<p class="muted">Matched, score ${meeting.match.score}: ${escapeHtml(meeting.match.why.join("; "))}</p>`
    : "";

  const warnings = meeting.warns.length
    ? `<p><strong>Data notes</strong></p>
       <ul>${meeting.warns.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul>`
    : "";

  return `
    ${ids}
    ${match}
    <table class="fields">
      <thead>
        <tr>
          <th scope="col"></th>
          <th scope="col">CRM said</th>
          <th scope="col">Calendar said</th>
          <th scope="col">Shown</th>
          <th scope="col">Source</th>
        </tr>
      </thead>
      <tbody>${fieldRows}</tbody>
    </table>
    ${warnings}`;
}

function renderSources(where) {
  if (where === "both") return `${badge("crm", "CRM")} ${badge("cal", "Calendar")}`;
  if (where === "crm") return badge("crm", "CRM only");
  return badge("cal", "Calendar only");
}

function renderFlags(meeting) {
  const flags = meeting.conflicts.map((name) => badge("conflict", `${FIELD_LABELS[name]} conflict`));
  if (meeting.ids.cal.length > 1) flags.push(badge("diff", "duplicate merged"));
  if (meeting.recurring) flags.push(badge("filled", "recurring"));
  return flags.join(" ");
}

function renderMeeting(meeting) {
  const id = escapeHtml(meeting.id);
  return `
    <tr class="meeting-row" data-id="${id}" tabindex="0" aria-expanded="false">
      <td>${escapeHtml(formatTime(meeting.start))}</td>
      <td>${escapeHtml(meeting.title)}</td>
      <td>${escapeHtml(meeting.type ?? "?")}</td>
      <td>${escapeHtml(meeting.status ?? "?")}</td>
      <td>${renderSources(meeting.where)}</td>
      <td>${renderFlags(meeting)}</td>
    </tr>
    <tr class="meeting-detail" id="detail-${id}" hidden>
      <td colspan="6">${renderDetail(meeting)}</td>
    </tr>`;
}

function renderMeetings(meetings) {
  dom.meetings.innerHTML = meetings.length
    ? meetings.map(renderMeeting).join("")
    : '<tr><td colspan="6">No meetings match.</td></tr>';
}

function renderReport(report) {
  const duplicates = report.dups
    .map((d) => `<li>${escapeHtml(d.dropped.join(", "))} merged into ${escapeHtml(d.kept)} (${escapeHtml(d.src)})</li>`)
    .join("");
  const warnings = report.warns
    .map((w) => `<li><strong>${escapeHtml(w.src)} ${escapeHtml(w.id)}</strong>: ${escapeHtml(w.msg)}</li>`)
    .join("");

  dom.report.innerHTML = `
    <p><strong>Duplicates merged</strong></p>
    <ul>${duplicates || "<li>none</li>"}</ul>
    <p><strong>Data warnings (${report.warns.length})</strong></p>
    <ul>${warnings || "<li>none</li>"}</ul>`;
}

/* ---------- Data loading ---------- */

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json();
}

function currentQuery() {
  const params = new URLSearchParams();
  if (dom.search.value) params.set("q", dom.search.value);
  if (dom.source.value) params.set("where", dom.source.value);
  if (dom.conflictsOnly.checked) params.set("conflict", "true");
  return params.toString();
}

async function load() {
  try {
    const [list, report] = await Promise.all([
      fetchJson(`/api/meetings?${currentQuery()}`),
      fetchJson("/api/report"),
    ]);
    renderStats(report.counts, report.dups.length);
    renderReport(report);
    renderMeetings(list.meetings);
  } catch (error) {
    dom.meetings.innerHTML = `<tr><td colspan="6">Could not load meetings: ${escapeHtml(error.message)}</td></tr>`;
  }
}

async function resync() {
  await fetchJson("/api/sync", { method: "POST" });
  await load();
}

/* ---------- Events ---------- */

function toggleDetail(row) {
  const detail = document.getElementById(`detail-${row.dataset.id}`);
  detail.hidden = !detail.hidden;
  row.setAttribute("aria-expanded", String(!detail.hidden));
}

// One listener on the table body covers every row, including re-rendered ones.
dom.meetings.addEventListener("click", (event) => {
  const row = event.target.closest(".meeting-row");
  if (row) toggleDetail(row);
});

dom.meetings.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const row = event.target.closest(".meeting-row");
  if (!row) return;
  event.preventDefault();
  toggleDetail(row);
});

[dom.search, dom.source, dom.conflictsOnly].forEach((control) =>
  control.addEventListener("input", load)
);
dom.sync.addEventListener("click", resync);

load();
