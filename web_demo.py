#!/usr/bin/env python3
"""
Web UI to compare Baseline Chatbot vs Tool-Aware (hallucination) vs ReAct Agent.

  python web_demo.py
  python web_demo.py --port 8080

Open http://127.0.0.1:5000

Modes:
  - Simulate (default): instant canned traces — no API key needed
  - Live: set USE_LIVE_LLM=1 in .env or pass --live
"""
import json
import os
import sys

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.demo.mock_metrics import enrich_mock_entry
from src.demo.scenarios import SCENARIOS
from src.telemetry.metrics import build_comparison_evaluation

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "web")
MOCK_PATH = os.path.join(WEB_DIR, "mock_traces.json")

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="")


def _load_mock() -> dict:
    with open(MOCK_PATH, encoding="utf-8") as f:
        return json.load(f)


def _use_live() -> bool:
    return os.getenv("USE_LIVE_LLM", "").lower() in ("1", "true", "yes")


def _run_mode(mode: str, query: str, llm=None) -> dict:
    from src.agent.agent import ReActAgent
    from src.agent.agent_v2 import ReActAgentV2
    from src.chatbot.baseline import BaselineChatbot
    from src.chatbot.tool_aware import ToolAwareChatbot

    if mode == "baseline":
        return BaselineChatbot(llm).run(query)
    if mode == "tool_aware":
        return ToolAwareChatbot(llm).run(query)
    if mode == "agent":
        return ReActAgent(llm, max_steps=5).run(query)
    if mode == "agent_v2":
        return ReActAgentV2(llm, max_steps=6).run(query)
    raise ValueError(f"Unknown mode: {mode}")


def _safe_run_mode(mode: str, query: str, llm=None) -> dict:
    try:
        return _run_mode(mode, query, llm)
    except Exception as exc:
        from src.telemetry.metrics import build_run_metrics

        return {
            "answer": f"Agent error: {exc}",
            "mode": mode,
            "used_tools": False,
            "steps": 0,
            "trace": [{"type": "error", "content": str(exc)}],
            "failures": [{"code": "RUNTIME_ERROR", "detail": str(exc)}],
            "metrics": build_run_metrics("error", "n/a", {}, 0, llm_calls=0),
        }


def _compare_payload(
    query: str,
    baseline: dict,
    tool_aware: dict,
    agent: dict,
    agent_v2: dict,
    simulate: bool,
) -> dict:
    modes = {
        "baseline": baseline,
        "tool_aware": tool_aware,
        "agent": agent,
        "agent_v2": agent_v2,
    }
    return {
        "query": query,
        "simulate": simulate,
        **modes,
        "evaluation": build_comparison_evaluation(modes),
    }


def _mock_compare_payload(scenario_key: str, query: str) -> dict:
    mock = _load_mock()
    entry = enrich_mock_entry(dict(mock[scenario_key]), scenario_key)
    agent_v2 = entry.get("agent_v2")
    if not agent_v2:
        agent_v2 = dict(entry.get("agent", {}))
        agent_v2["mode"] = "react_agent_v2"
        agent_v2.setdefault("failures", [])
        agent_v2["metrics"] = entry.get("agent", {}).get("metrics")
    return _compare_payload(
        query,
        entry["baseline"],
        entry["tool_aware"],
        entry["agent"],
        agent_v2,
        simulate=True,
    )


@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/api/scenarios")
def api_scenarios():
    return jsonify(SCENARIOS)


@app.get("/api/config")
def api_config():
    return jsonify({"live_llm": _use_live(), "mock_available": os.path.exists(MOCK_PATH)})


@app.post("/api/compare")
def api_compare():
    body = request.get_json(force=True) or {}
    query = body.get("query", "").strip()
    scenario_id = body.get("scenario_id")
    simulate = body.get("simulate", not _use_live())

    if simulate and scenario_id:
        key = str(scenario_id)
        mock = _load_mock()
        if key in mock:
            q = query or SCENARIOS[int(scenario_id) - 1]["query"]
            return jsonify(_mock_compare_payload(key, q))

    if not query:
        return jsonify({"error": "query or scenario_id required"}), 400

    try:
        from src.core.factory import get_llm_provider

        llm = get_llm_provider()
    except ValueError as exc:
        return jsonify({"error": str(exc), "hint": "Use simulate mode or set API keys in .env"}), 503

    baseline = _safe_run_mode("baseline", query, llm)
    tool_aware = _safe_run_mode("tool_aware", query, llm)
    agent = _safe_run_mode("agent", query, llm)
    agent_v2 = _safe_run_mode("agent_v2", query, llm)
    return jsonify(_compare_payload(query, baseline, tool_aware, agent, agent_v2, simulate=False))


@app.post("/api/run")
def api_run():
    body = request.get_json(force=True) or {}
    mode = body.get("mode", "agent")
    query = body.get("query", "").strip()
    if not query:
        return jsonify({"error": "query required"}), 400

    if body.get("simulate", not _use_live()):
        return jsonify({"error": "Single-mode simulate uses /api/compare with scenario_id"}), 400

    try:
        from src.core.factory import get_llm_provider

        llm = get_llm_provider()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 503

    return jsonify(_run_mode(mode, query, llm))


def main():
    import argparse

    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.getenv("WEB_DEMO_PORT", "5000")))
    parser.add_argument("--live", action="store_true", help="Use real LLM instead of mock traces")
    args = parser.parse_args()
    if args.live:
        os.environ["USE_LIVE_LLM"] = "1"

    print(f"Lab 3 Web Demo: http://127.0.0.1:{args.port}")
    print(f"Mode: {'LIVE LLM' if _use_live() else 'SIMULATE (mock traces, no API key)'}")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
