let scenarios = [];
let selectedScenarioId = 1;
let liveLlm = false;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

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
  const meta = panelEl.querySelector(".meta");
  const answer = panelEl.querySelector(".answer");
  const traceWrap = panelEl.querySelector(".trace-wrap");
  const traceOl = panelEl.querySelector(".trace");

  meta.innerHTML = "";
  if (data.warning) {
    const w = document.createElement("div");
    w.className = "warning" + (data.warning.includes("FAKE") ? " fake" : "");
    w.textContent = data.warning;
    meta.appendChild(w);
  }
  const info = document.createElement("div");
  info.textContent = `Steps: ${data.steps} · Tools executed: ${data.used_tools ? "yes" : "no"}`;
  meta.appendChild(info);

  answer.textContent = data.answer || "(no answer)";

  traceOl.innerHTML = "";
  const trace = data.trace || [];
  if (trace.length === 0) {
    traceWrap.classList.add("hidden");
    return;
  }
  traceWrap.classList.remove("hidden");
  trace.forEach((step, i) => {
    const li = document.createElement("li");
    li.className = step.type;
    li.style.animationDelay = `${i * 0.12}s`;
    li.innerHTML = `<span class="kind">${step.type}</span>${escapeHtml(step.content)}`;
    traceOl.appendChild(li);
  });
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

async function runComparison() {
  const query = $("#queryInput").value.trim();
  if (!query) return;

  $("#runBtn").disabled = true;
  $("#loading").classList.remove("hidden");
  clearPanels();

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
    panel.querySelector(".answer").textContent = "";
    panel.querySelector(".trace").innerHTML = "";
  });
}

$("#runBtn").addEventListener("click", runComparison);
$("#liveToggle").addEventListener("change", () => {
  liveLlm = $("#liveToggle").checked;
  updateModeBadge();
});

init();
