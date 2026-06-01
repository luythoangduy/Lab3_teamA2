let scenarios = [];
let selectedScenarioId = 1;
let liveLlm = false;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const EMPTY_PANEL = {
  answer: "(no data — run comparison again)",
  steps: 0,
  used_tools: false,
  trace: [],
  failures: [],
};

async function init() {
  const [scRes, cfgRes] = await Promise.all([
    fetch("/api/scenarios"),
    fetch("/api/config"),
  ]);
  scenarios = await scRes.json();
  const cfg = await cfgRes.json();
  liveLlm = cfg.live_llm;
  $("#liveToggle").checked = liveLlm;
  updateModeBadge();
  renderChips();
  selectScenario(1);
}

function updateModeBadge() {
  const badge = $("#modeBadge");
  if (liveLlm) {
    badge.textContent = "Live LLM";
    badge.className = "badge live";
  } else {
    badge.textContent = "Simulate";
    badge.className = "badge simulate";
  }
}

function renderChips() {
  const container = $("#scenarioChips");
  container.innerHTML = "";
  scenarios.forEach((s) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip" + (s.id === selectedScenarioId ? " active" : "");
    const hall = (s.tags || []).includes("hallucination")
      ? ' <span class="tag-hallucination">⚠ hallucination</span>'
      : "";
    btn.innerHTML = `${s.id}. ${s.name}${hall}`;
    btn.onclick = () => selectScenario(s.id);
    container.appendChild(btn);
  });
}

function selectScenario(id) {
  selectedScenarioId = id;
  const s = scenarios.find((x) => x.id === id);
  if (!s) return;
  $("#queryInput").value = s.query;
  $("#scenarioExpect").textContent = "Expected: " + s.expect;
  $$(".chip").forEach((el, i) => {
    el.classList.toggle("active", scenarios[i].id === id);
  });
}

function renderPanel(panelEl, data) {
  const payload = data && typeof data === "object" ? data : EMPTY_PANEL;
  const meta = panelEl.querySelector(".meta");
  const answer = panelEl.querySelector(".answer");
  const traceWrap = panelEl.querySelector(".trace-wrap");
  const traceOl = panelEl.querySelector(".trace");

  meta.innerHTML = "";
  if (payload.warning) {
    const w = document.createElement("div");
    w.className = "warning" + (payload.warning.includes("FAKE") ? " fake" : "");
    w.textContent = payload.warning;
    meta.appendChild(w);
  }
  if (payload.failures && payload.failures.length) {
    const f = document.createElement("div");
    f.className = "warning";
    f.textContent = `Failures handled: ${payload.failures.map((x) => x.code).join(", ")}`;
    meta.appendChild(f);
  }
  const info = document.createElement("div");
  let line = `Steps: ${payload.steps ?? 0} · Tools executed: ${payload.used_tools ? "yes" : "no"}`;
  if (payload.images_preserved) line += " · images preserved";
  if (payload.mode) line += ` · ${payload.mode}`;
  info.textContent = line;
  meta.appendChild(info);

  if (payload.metrics) {
    const m = document.createElement("div");
    m.className = "metrics";
    m.innerHTML = formatMetricsHtml(payload.metrics);
    meta.appendChild(m);
  }

  const answerText = payload.answer || "(no answer)";
  if (panelEl.querySelector(".answer-md") && answerText.includes("![")) {
    answer.innerHTML = renderMarkdownImages(answerText);
  } else {
    answer.textContent = answerText;
  }

  traceOl.innerHTML = "";
  const trace = [...(payload.trace || [])];
  (payload.failures || []).forEach((f) => {
    trace.push({
      type: "failure",
      content: `${f.code}${f.recovery ? " → " + f.recovery : ""}${f.detail ? ": " + f.detail : ""}`,
    });
  });

  if (trace.length === 0) {
    traceWrap.classList.add("hidden");
    return;
  }
  traceWrap.classList.remove("hidden");
  trace.forEach((step, i) => {
    const li = document.createElement("li");
    li.className = step.type || "step";
    li.style.animationDelay = `${i * 0.12}s`;
    li.innerHTML = `<span class="kind">${step.type}</span>${escapeHtml(step.content || "")}`;
    traceOl.appendChild(li);
  });
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function formatMetricsHtml(m) {
  const sim = m.simulated ? ' <span class="sim-tag">simulate</span>' : "";
  const cost =
    m.cost_usd != null
      ? `$${Number(m.cost_usd).toFixed(6)}`
      : "—";
  return (
    `<strong>Tokens / cost</strong>${sim}<br>` +
    `Calls: ${m.llm_calls ?? 0} · ` +
    `Prompt: ${m.prompt_tokens ?? 0} · ` +
    `Completion: ${m.completion_tokens ?? 0} · ` +
    `Total: ${m.total_tokens ?? 0}<br>` +
    `Latency: ${m.latency_ms ?? 0} ms · Est. cost: ${cost}`
  );
}

function renderEvaluationSummary(evaluation, simulate) {
  const section = $("#evaluationSummary");
  const tbody = $("#evaluationTableBody");
  if (!evaluation || !evaluation.per_mode) {
    section.classList.add("hidden");
    return;
  }
  section.classList.remove("hidden");
  const t = evaluation.totals || {};
  const simNote = simulate || evaluation.simulated ? " (simulated estimates)" : " (live API usage)";
  $("#evaluationTotals").textContent =
    `Totals${simNote}: ${t.llm_calls ?? 0} LLM calls · ` +
    `${t.total_tokens ?? 0} tokens · ` +
    `${t.latency_ms ?? 0} ms · ` +
    `$${Number(t.cost_usd ?? 0).toFixed(6)} USD`;

  tbody.innerHTML = "";
  const labels = {
    baseline: "① Baseline",
    tool_aware: "② Tool-aware",
    agent: "③ Agent v1",
    agent_v2: "④ Agent v2",
  };
  evaluation.per_mode.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${labels[row.mode] || row.mode}</td>
      <td>${row.llm_calls ?? 0}</td>
      <td>${row.prompt_tokens ?? 0}</td>
      <td>${row.completion_tokens ?? 0}</td>
      <td>${row.total_tokens ?? 0}</td>
      <td>${row.latency_ms ?? 0} ms</td>
      <td>$${Number(row.cost_usd ?? 0).toFixed(6)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderMarkdownImages(text) {
  const escaped = escapeHtml(text);
  return escaped.replace(
    /!\[([^\]]*)\]\(([^)]+)\)/g,
    '<img alt="$1" src="$2" loading="lazy" />'
  );
}

async function runComparison() {
  const query = $("#queryInput").value.trim();
  if (!query) return;

  $("#runBtn").disabled = true;
  $("#loading").classList.remove("hidden");
  clearPanels();
  $("#evaluationSummary").classList.add("hidden");

  try {
    const res = await fetch("/api/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        scenario_id: selectedScenarioId,
        simulate: !$("#liveToggle").checked,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.error || "Request failed");
      return;
    }
    renderPanel($('.panel[data-mode="baseline"]'), data.baseline);
    renderPanel($('.panel[data-mode="tool_aware"]'), data.tool_aware);
    renderPanel($('.panel[data-mode="agent"]'), data.agent);
    renderPanel($('.panel[data-mode="agent_v2"]'), data.agent_v2 || EMPTY_PANEL);
    renderEvaluationSummary(data.evaluation, data.simulate);
  } catch (e) {
    alert("Network error: " + e.message);
  } finally {
    $("#runBtn").disabled = false;
    $("#loading").classList.add("hidden");
  }
}

function clearPanels() {
  $$(".panel").forEach((panel) => {
    panel.querySelector(".meta").innerHTML = "";
    const answer = panel.querySelector(".answer");
    answer.innerHTML = "";
    answer.textContent = "";
    const traceWrap = panel.querySelector(".trace-wrap");
    traceWrap.classList.remove("hidden");
    panel.querySelector(".trace").innerHTML = "";
  });
}

$("#runBtn").addEventListener("click", runComparison);
$("#liveToggle").addEventListener("change", () => {
  liveLlm = $("#liveToggle").checked;
  updateModeBadge();
});

init();
