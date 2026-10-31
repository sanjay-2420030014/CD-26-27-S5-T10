/* LexiScan – front-end logic.
 * The page never tokenizes anything itself: it sends the source code to the
 * Flask backend (POST /api/analyze) and displays the JSON that comes back. */
"use strict";

// ---------------------------------------------------------------------------
// Sample programs
// ---------------------------------------------------------------------------
const SAMPLE_VALID = `#include <stdio.h>

int main() {
    int age = 20;
    float marks = 85.5;

    if (age >= 18) {
        printf("Eligible");
    } else {
        printf("Not Eligible");
    }

    return 0;
}
`;

const SAMPLE_ERRORS = `#include <stdio.h>

int main() {
    // invalid identifier (starts with a digit)
    int 2count = 10;
    // malformed numeric literal
    float price = 12.5.3;
    // invalid characters @ and $
    int total@ = 5 $ 3;
    // more than one character in a character literal
    char grade = 'AB';
    // unterminated character literal
    char initial = 'x;
    // unterminated string literal
    char *msg = "Hello World;
    return 0;
}
/* this block comment is never closed
`;

// ---------------------------------------------------------------------------
// Token type metadata (label + chart colour; colours match the CSS badges)
// ---------------------------------------------------------------------------
const TYPE_INFO = {
  KEYWORD:        { label: "Keyword",           color: "#1a3a8f" },
  IDENTIFIER:     { label: "Identifier",        color: "#0f7b8a" },
  OPERATOR:       { label: "Operator",          color: "#b25e0a" },
  CONSTANT:       { label: "Constant",          color: "#6a3fb5" },
  STRING_LITERAL: { label: "String Literal",    color: "#1c8a55" },
  CHAR_LITERAL:   { label: "Character Literal", color: "#3d8a1c" },
  DELIMITER:      { label: "Delimiter",         color: "#55627f" },
  COMMENT:        { label: "Comment",           color: "#8a8f9c" },
  PREPROCESSOR:   { label: "Preprocessor",      color: "#a02a74" },
};

const VIEWS = ["home", "editor", "results", "theory", "about"];
const MAX_ROWS = 5000;          // rows drawn in a table at once
const MAX_LEXEME_SHOWN = 120;   // longer lexemes are shortened on screen

let result = null;              // last analysis returned by the server

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------------------
// Small DOM helpers (text is always set with textContent, never innerHTML,
// because lexemes come from arbitrary user input)
// ---------------------------------------------------------------------------
function makeCell(text, className) {
  const td = document.createElement("td");
  td.textContent = text;
  if (className) td.className = className;
  return td;
}

function makeRow(cells, className) {
  const tr = document.createElement("tr");
  if (className) tr.className = className;
  cells.forEach((c) => tr.appendChild(c));
  return tr;
}

function shorten(text) {
  return text.length > MAX_LEXEME_SHOWN ? text.slice(0, MAX_LEXEME_SHOWN) + "…" : text;
}

function lexemeCell(lexeme) {
  const td = makeCell(shorten(lexeme), "mono");
  if (lexeme.length > MAX_LEXEME_SHOWN) td.title = lexeme;
  return td;
}

function typeBadgeCell(type) {
  const td = document.createElement("td");
  const span = document.createElement("span");
  span.className = "badge t-" + type;
  span.textContent = (TYPE_INFO[type] || { label: type }).label;
  td.appendChild(span);
  return td;
}

function noteRow(text, colspan) {
  const td = makeCell(text);
  td.colSpan = colspan;
  td.className = "muted";
  return makeRow([td]);
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------
function showView(name) {
  if (!VIEWS.includes(name)) name = "home";
  VIEWS.forEach((v) => { $("view-" + v).hidden = v !== name; });
  document.querySelectorAll("[data-nav]").forEach((a) => {
    a.classList.toggle("active", a.dataset.nav === name && a.closest(".nav") !== null);
  });
  window.scrollTo(0, 0);
}

function go(name) {
  showView(name);                     // switch immediately
  if (location.hash !== "#" + name) location.hash = name;   // keep the URL in sync
}

window.addEventListener("hashchange", () => showView(location.hash.slice(1)));

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------
const sourceEl = $("source");

function setMessage(text, isError) {
  const msg = $("editor-msg");
  msg.textContent = text;
  msg.className = isError ? "error" : "";
}

function updateEditor() {
  const text = sourceEl.value;
  const lines = text.split("\n").length;
  let numbers = "";
  for (let i = 1; i <= lines; i++) numbers += i + (i < lines ? "\n" : "");
  $("gutter").textContent = numbers;
  $("gutter").scrollTop = sourceEl.scrollTop;
  $("editor-info").textContent =
    lines + (lines === 1 ? " line" : " lines") + " · " + text.length + " characters";
}

function loadSource(text, message) {
  sourceEl.value = text;
  updateEditor();
  setMessage(message, false);
}

sourceEl.addEventListener("input", () => { updateEditor(); setMessage("", false); });
sourceEl.addEventListener("scroll", () => { $("gutter").scrollTop = sourceEl.scrollTop; });

$("btn-sample").addEventListener("click", () => loadSource(SAMPLE_VALID, "Sample program loaded."));
$("btn-sample-errors").addEventListener("click", () => loadSource(SAMPLE_ERRORS, "Error sample loaded."));
$("btn-clear-code").addEventListener("click", () => { loadSource("", ""); sourceEl.focus(); });
$("btn-start").addEventListener("click", () => go("editor"));
$("btn-go-editor").addEventListener("click", () => go("editor"));

// ---------------------------------------------------------------------------
// Analyze: send the code to the Flask backend
// ---------------------------------------------------------------------------
async function analyze() {
  const source = sourceEl.value;
  if (!source.trim()) {
    setMessage("Source code is empty. Please enter some code to analyze.", true);
    return;
  }

  const button = $("btn-analyze");
  button.disabled = true;
  setMessage("Analyzing…", false);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: source }),
    });
    let data = null;
    try { data = await response.json(); } catch (e) { /* not JSON */ }

    if (!response.ok || !data || !data.ok) {
      setMessage((data && data.error) || "Server error (" + response.status + ").", true);
      return;
    }
    result = data;
    renderAll();
    setMessage("", false);
    go("results");
    activateTab("summary");
  } catch (err) {
    setMessage("Could not reach the server. Make sure app.py is running.", true);
  } finally {
    button.disabled = false;
  }
}

$("btn-analyze").addEventListener("click", analyze);

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function renderAll() {
  $("results-empty").hidden = true;
  $("results-body").hidden = false;
  renderDashboard();
  renderSummary();
  renderTokens();
  renderStats();
  renderErrors();
  renderLines();
}

function renderDashboard() {
  const s = result ? result.stats : null;
  $("dash-total").textContent = s ? s.total_tokens : 0;
  $("dash-keywords").textContent = s ? s.keywords : 0;
  $("dash-identifiers").textContent = s ? s.identifiers : 0;
  $("dash-errors").textContent = s ? s.errors : 0;
  $("dash-note").textContent = result
    ? "Based on the last analysis (" + result.summary.lines + " lines of source code)."
    : "No analysis yet. Open the editor and click “Analyze Code”.";
}

function renderSummary() {
  const { stats, summary } = result;
  const banner = $("summary-banner");
  if (stats.errors === 0) {
    banner.className = "banner ok";
    banner.textContent = "Analysis completed successfully. No lexical errors were found.";
  } else {
    banner.className = "banner";
    banner.textContent = "Analysis completed with " + stats.errors +
      (stats.errors === 1 ? " lexical error." : " lexical errors.");
  }
  $("sum-tokens").textContent = stats.total_tokens;
  $("sum-errors").textContent = stats.errors;
  $("sum-lines").textContent = summary.lines;
  $("sum-chars").textContent = summary.characters;
  $("sum-time").textContent = "Scanned in " + summary.elapsed_ms + " ms.";
}

// ---- tokens: search + filter --------------------------------------------
function visibleTokens() {
  if (!result) return [];
  const query = $("token-search").value.trim().toLowerCase();
  const type = $("token-filter").value;
  return result.tokens.filter((t) => {
    if (type && t.type !== type) return false;
    if (!query) return true;
    const label = (TYPE_INFO[t.type] || { label: t.type }).label.toLowerCase();
    return t.lexeme.toLowerCase().includes(query) ||
           label.includes(query) ||
           t.type.toLowerCase().includes(query) ||
           String(t.line) === query ||
           String(t.column) === query;
  });
}

function renderTokens() {
  const tbody = $("token-table").tBodies[0];
  tbody.textContent = "";
  const list = visibleTokens();
  const frag = document.createDocumentFragment();

  list.slice(0, MAX_ROWS).forEach((t, i) => {
    frag.appendChild(makeRow([
      makeCell(i + 1, "num"),
      lexemeCell(t.lexeme),
      typeBadgeCell(t.type),
      makeCell(t.line, "num"),
      makeCell(t.column, "num"),
    ]));
  });
  if (list.length === 0) frag.appendChild(noteRow("No tokens match the current search / filter.", 5));
  tbody.appendChild(frag);

  let text = "Showing " + list.length + " of " + (result ? result.tokens.length : 0) + " tokens.";
  if (list.length > MAX_ROWS) text += " Only the first " + MAX_ROWS + " rows are drawn; the CSV contains all of them.";
  $("token-count").textContent = text;
}

$("token-search").addEventListener("input", renderTokens);
$("token-filter").addEventListener("change", renderTokens);

// ---- CSV download ---------------------------------------------------------
function csvLexeme(value) {
  let s = String(value);
  // Stop spreadsheet programs from treating a lexeme such as "=" or "+" as a formula.
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function downloadCsv() {
  if (!result) return;
  const rows = ["Lexeme,Token Type,Line Number,Column Number"];
  visibleTokens().forEach((t) => {
    rows.push([csvLexeme(t.lexeme), t.type, t.line, t.column].join(","));
  });
  // The BOM lets Excel open the file as UTF-8.
  const blob = new Blob(["﻿" + rows.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "lexiscan_tokens.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

$("btn-csv").addEventListener("click", downloadCsv);

// ---- statistics -------------------------------------------------------------
function renderStats() {
  const s = result.stats;
  const cards = [
    ["Total tokens", s.total_tokens, false],
    ["Keywords", s.keywords, false],
    ["Identifiers", s.identifiers, false],
    ["Operators", s.operators, false],
    ["Constants", s.constants, false],
    ["Delimiters", s.delimiters, false],
    ["String literals", s.string_literals, false],
    ["Character literals", s.char_literals, false],
    ["Comments", s.comments, false],
    ["Preprocessor lines", s.preprocessor, false],
    ["Lexical errors", s.errors, true],
  ];
  const holder = $("stat-cards");
  holder.textContent = "";
  cards.forEach(([label, value, danger]) => {
    const card = document.createElement("div");
    card.className = "stat-card" + (danger ? " danger" : "");
    const l = document.createElement("span");
    l.className = "stat-label";
    l.textContent = label;
    const v = document.createElement("span");
    v.className = "stat-value";
    v.textContent = value;
    card.append(l, v);
    holder.appendChild(card);
  });
  renderBarChart(s.by_type);
  renderDonutChart(s.by_type, s.total_tokens);
}

function renderBarChart(byType) {
  const holder = $("bar-chart");
  holder.textContent = "";
  const max = Math.max(1, ...Object.values(byType));
  Object.keys(TYPE_INFO).forEach((type) => {
    const count = byType[type] || 0;
    const row = document.createElement("div");
    row.className = "bar-row";
    const name = document.createElement("span");
    name.textContent = TYPE_INFO[type].label;
    const track = document.createElement("div");
    track.className = "bar-track";
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = (count / max * 100) + "%";
    fill.style.background = TYPE_INFO[type].color;
    track.appendChild(fill);
    const num = document.createElement("span");
    num.className = "bar-num";
    num.textContent = count;
    row.append(name, track, num);
    holder.appendChild(row);
  });
}

function renderDonutChart(byType, total) {
  const holder = $("donut-chart");
  holder.textContent = "";
  if (total === 0) {
    holder.textContent = "No tokens to chart.";
    return;
  }
  const NS = "http://www.w3.org/2000/svg";
  const R = 70;
  const C = 2 * Math.PI * R;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 200 200");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Token distribution donut chart");

  const legend = document.createElement("ul");
  legend.className = "legend";

  let offset = 0;
  Object.keys(TYPE_INFO).forEach((type) => {
    const count = byType[type] || 0;
    if (count === 0) return;
    const length = count / total * C;
    const arc = document.createElementNS(NS, "circle");
    arc.setAttribute("cx", 100);
    arc.setAttribute("cy", 100);
    arc.setAttribute("r", R);
    arc.setAttribute("fill", "none");
    arc.setAttribute("stroke", TYPE_INFO[type].color);
    arc.setAttribute("stroke-width", 28);
    arc.setAttribute("stroke-dasharray", length + " " + (C - length));
    arc.setAttribute("stroke-dashoffset", -offset);
    arc.setAttribute("transform", "rotate(-90 100 100)");
    svg.appendChild(arc);
    offset += length;

    const li = document.createElement("li");
    const swatch = document.createElement("i");
    swatch.style.background = TYPE_INFO[type].color;
    const text = document.createElement("span");
    text.textContent = TYPE_INFO[type].label + " – " + count + " (" + (count / total * 100).toFixed(1) + "%)";
    li.append(swatch, text);
    legend.appendChild(li);
  });

  const centre = document.createElementNS(NS, "text");
  centre.setAttribute("x", 100);
  centre.setAttribute("y", 106);
  centre.setAttribute("text-anchor", "middle");
  centre.setAttribute("font-size", 24);
  centre.setAttribute("font-weight", 700);
  centre.setAttribute("fill", "#0b1b3a");
  centre.textContent = total;
  svg.appendChild(centre);

  const wrap = document.createElement("div");
  wrap.className = "donut-wrap";
  wrap.append(svg, legend);
  holder.appendChild(wrap);
}

// ---- lexical errors ---------------------------------------------------------
function renderErrors() {
  const errors = result.errors;
  const tbody = $("error-table").tBodies[0];
  tbody.textContent = "";
  errors.forEach((e, i) => {
    tbody.appendChild(makeRow([
      makeCell(i + 1, "num"),
      makeCell(e.message),
      makeCell(e.line, "num"),
      makeCell(e.column, "num"),
      lexemeCell(e.lexeme),
    ]));
  });
  $("errors-ok").hidden = errors.length > 0;
  $("errors-table-wrap").hidden = errors.length === 0;
  const pill = $("tab-error-count");
  pill.textContent = errors.length;
  pill.classList.toggle("zero", errors.length === 0);
}

// ---- source line information ------------------------------------------------
function renderLines() {
  const tbody = $("line-table").tBodies[0];
  tbody.textContent = "";
  const frag = document.createDocumentFragment();
  result.lines.slice(0, MAX_ROWS).forEach((info) => {
    frag.appendChild(makeRow([
      makeCell(info.line, "num"),
      makeCell(info.text, "mono"),
      makeCell(info.tokens, "num"),
      makeCell(info.errors, "num"),
    ], info.errors > 0 ? "has-error" : ""));
  });
  if (result.lines.length > MAX_ROWS) {
    frag.appendChild(noteRow("Only the first " + MAX_ROWS + " lines are shown.", 4));
  }
  tbody.appendChild(frag);
}

// ---------------------------------------------------------------------------
// Result tabs and clearing
// ---------------------------------------------------------------------------
function activateTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.tab === name;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.hidden = panel.id !== "tab-" + name;
  });
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.tab));
});

function clearAnalysis() {
  result = null;
  $("results-body").hidden = true;
  $("results-empty").hidden = false;
  $("token-search").value = "";
  $("token-filter").value = "";
  ["token-table", "error-table", "line-table"].forEach((id) => { $(id).tBodies[0].textContent = ""; });
  $("stat-cards").textContent = "";
  $("bar-chart").textContent = "";
  $("donut-chart").textContent = "";
  renderDashboard();
}

$("btn-clear-analysis").addEventListener("click", clearAnalysis);

// ---------------------------------------------------------------------------
// Start-up
// ---------------------------------------------------------------------------
loadSource(SAMPLE_VALID, "");        // the sample program is in the editor from the start
showView(location.hash.slice(1));
