# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Minh (minhh branch owner)
- **Student ID**: [2A202600963]
- **Date**: 2026-06-01
- **Team**: Team A2 — Minh (minhh), Đạt (dat), Duy (duyhk), Dũng

---

## I. Technical Contribution (15 Points)

### Overview

My main responsibility was building the **comparison demo stack**: two chatbot baselines, ReAct Agent v1 and v2, the Flask web UI, terminal runner, token/cost telemetry wiring, and merge integration with teammates’ SQLite catalog work (duyhk) and evaluation suite (dat).

### Modules implemented / led

| Area | Files | What I did |
|:---|:---|:---|
| **Baseline chatbot** | `src/chatbot/baseline.py` | LLM-only assistant with no tools — demonstrates content hallucination on catalog facts. |
| **Tool-aware chatbot** | `src/chatbot/tool_aware.py` | Tools listed in system prompt but **never executed** — demonstrates fake `Observation:` hallucination. |
| **ReAct Agent v1** | `src/agent/agent.py` | Full Thought → Action → Observation loop, parse retry on format errors, tool execution, trace + `metrics` in response. |
| **ReAct Agent v2** | `src/agent/agent_v2.py` | Guardrails (parse retry, duplicate-action block, `HALLUCINATED_TOOL`, empty-result recovery), image carry-over into `Final Answer`, structured `failures[]`. |
| **Product tools (early + fixes)** | `src/tools/product_tools.py` | Initial API-based tools; after merge kept duyhk’s SQLite `ProductCatalog` and fixed `_parse_category()` for JSON args like `{"category": "beauty"}`. |
| **Provider factory** | `src/core/factory.py` | `get_llm_provider()` for OpenAI / Gemini / local with lazy local import. |
| **Demo scenarios** | `src/demo/scenarios.py` | Four lab scenarios (hallucination trap, cheapest+stock, id lookup, search+compare). |
| **Terminal compare** | `demo_compare.py` | Side-by-side run of all four modes + `--simulate` for mock metrics. |
| **Web demo** | `web_demo.py`, `web/*` | Flask API, 4-column UI, simulate vs live, evaluation summary table. |
| **Mock traces** | `web/mock_traces.json`, `src/demo/mock_metrics.py` | Canned answers + simulated token/cost per mode/scenario (no API key for demos). |
| **Telemetry helpers** | `src/telemetry/metrics.py` (extended) | `build_run_metrics()`, `build_comparison_evaluation()`, pricing for gpt-4o-mini / gpt-4o / Gemini. |
| **Merges** | multiple | Merged `origin/duyhk` and `origin/dat` into `minhh`, resolved conflicts in agent, tools, metrics, web. |

### Code highlights

**1. ReAct loop (v1)** — growing transcript + metrics per run:

```python
transcript = f"User: {user_input}"
while steps < self.max_steps:
    result = self.llm.generate(transcript, system_prompt=self.get_system_prompt())
    # parse Thought / Action / Final Answer → execute tool → append Observation
    transcript = f"{transcript}\n\nAssistant:\n{content}\nObservation: {observation}"
```

**2. Category argument fix (critical bug)** — tools now accept JSON from the model:

```python
def _parse_category(args: str) -> str:
    payload = _parse_args(args)
    if isinstance(payload, dict):
        return str(payload.get("category", payload.get("query", ""))).strip()
    return str(payload).strip().strip("\"'")
```

Before this fix, `cheapest_in_category({"category": "beauty"})` became category `"{'category': 'beauty'}"` and returned no products.

**3. Agent v2 failure taxonomy** — example guard after unknown tool:

```python
if tool_name not in self.valid_tool_names:
    return json.dumps({"error": "HALLUCINATED_TOOL", ...}), {"code": "HALLUCINATED_TOOL", ...}
```

**4. Web evaluation API** — all modes return `metrics` + comparison totals:

```python
return _compare_payload(query, baseline, tool_aware, agent, agent_v2, simulate=False)
# includes evaluation: { per_mode: [...], totals: { total_tokens, cost_usd, ... } }
```

### How my code fits the ReAct loop

- **Chatbots** sit *outside* the loop: one LLM call, no `Observation` from the environment.
- **Agent v1/v2** implement the loop: the LLM only sees grounded facts after `execute_tool()` appends real SQLite/API results.
- **v2** adds extra `Observation: GUARD: ...` lines in the transcript so the model recovers from parse errors, empty search, or duplicate actions without inventing catalog data.

### Teammate integration (not my solo work)

- **Duy (duyhk)**: SQLite `ProductCatalog`, heuristic search, markdown product cards with images.
- **Đạt (dat)**: `run_evaluation.py` (40-case suite), `report/EVALUATION_DASHBOARD.md`, group report draft, CLI cost printing in `product_chat.py`.

---

## II. Debugging Case Study (10 Points)

### Problem: “No products in beauty category” despite 100 items cached

**Symptom (Live web demo, Scenario 2)**  
Agent v1 and v2 answered that the beauty category was empty. Trace showed:

```text
Action: cheapest_in_category({"category": "beauty"})
Observation: No matching products found.
```

After `refresh_products`, v2 hit `DUPLICATE_ACTION` and still reported no beauty products.

**Log / trace source**  
`AGENT_TOOL_OBSERVATION` in `logs/` and web UI trace panel (scenario 2, live run).

**Diagnosis**

1. **Root cause (tool layer)**  
   `_parse_category()` used `str(dict)` on JSON arguments:

   ```python
   category = str(_parse_args('{"category": "beauty"}'))
   # → "{'category': 'beauty'}"  # wrong SQL category string
   ```

2. **Secondary cause (v2 guard)**  
   After a failed `cheapest_in_category`, the agent called `refresh_products` then tried the same action again. Duplicate-action guard blocked the retry even though the DB was now populated.

**Solution**

1. Added `_parse_category()` to read `payload["category"]` from JSON.
2. Replaced string-interpolated SQL in `cheapest_in_category` with parameterized query on `ProductCatalog`.
3. In v2, `seen_actions.clear()` after successful `refresh_products` so catalog refresh allows a legitimate retry.

**Result**  
`cheapest_in_category({"category": "beauty"})` returns **Red Nail Polish**, $8.99, stock 79, with thumbnail markdown image in v2 final answer.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning

The `Thought` block helped mainly for **multi-step** questions (e.g. search mascara → compare prices). For single-shot factual questions, it sometimes added latency without benefit. The scratchpad (`transcript`) mattered more than `Thought` alone: later steps only work because prior **Observations** are in context.

### 2. Reliability — when the agent did worse

| Case | Chatbot | Agent |
|:---|:---|:---|
| Simple chit-chat (“what categories do you sell?”) | Fast, fluent guess | Overkill; may call unnecessary tools |
| Missing product (Samsung S24) | Confident fake price | Correct “not found” after search — **agent wins** |
| Cheapest in category | Plausible guess (often wrong) | Correct after tool fix — **agent wins** |
| Tool-aware chatbot | Sounds authoritative | Invents `Observation:` JSON — **worst for trust** |

Agents are more reliable for **grounded catalog facts**; chatbots are cheaper (1 LLM call) but unsafe for numbers.

### 3. Observation feedback

Empty observation (`No matching products found`) pushed v2 to call `refresh_products` or broaden search — good.  
`HALLUCINATED_TOOL` + GUARD listing valid tools reduced invented tool names on the next step.  
Fake observations (tool-aware mode) show why **execution** must be separate from **prompt text**: describing tools ≠ using them.

### v1 vs v2 (my view)

- **v1**: simpler prompt + transcript; fewer moving parts.  
- **v2**: better for demos and grading (failures[], images, guards) but more tokens and more `Observation` lines.  
v2 “failure detection” is mostly **rule-based guardrails**, not an ML hallucination classifier — still valid for the lab’s telemetry and “Agent v2 improved” criterion.

---

## IV. Future Improvements (5 Points)

| Area | Proposal |
|:---|:---|
| **Memory** | Feed `self.history` into the next `run()` so follow-ups like “how much stock for that one?” work in `product_chat.py`. |
| **Messages API** | Refactor `LLMProvider` to use `messages=[...]` roles instead of one concatenated transcript string. |
| **Scalability** | Async tool calls; cache embeddings for `search_products` when catalog grows beyond SQLite. |
| **Safety** | Supervisor pass on `Final Answer` to block prices not present in any observation (content-level hallucination check). |
| **Evaluation** | Connect web UI to `run_evaluation.py` output so simulate mode and 40-case dashboard share one metrics pipeline (dat’s suite + my web layer). |

---

## Appendix: Git commits (minhh / nminh2209)

| Commit | Summary |
|:---|:---|
| `0b041dc` | Web demo, chatbots, scenarios, factory, initial tools |
| `1bf042f` / `6fbc8d3` | Merge duyhk; agent + SQLite tools integration |
| `3f7ea4e` | Agent v2, mock traces, category fix |
| `6c33df2` / metrics work | Token/cost metrics, evaluation table in web UI |
| `38d06d7` | Merge PR minhh → main |

---

> Submit as required by course: this file is `report/individual_reports/REPORT_Minh.md`.  
> Replace `[Fill in your student ID]` before submission.
