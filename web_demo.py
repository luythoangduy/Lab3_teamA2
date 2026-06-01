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

from src.demo.scenarios import SCENARIOS

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

    if scenario_id and simulate:
        mock = _load_mock()
        key = str(scenario_id)
        if key in mock:
            return jsonify(
                {
                    "query": SCENARIOS[int(scenario_id) - 1]["query"],
                    "simulate": True,
                    "baseline": mock[key]["baseline"],
                    "tool_aware": mock[key]["tool_aware"],
                    "agent": mock[key]["agent"],
                    "agent_v2": mock[key].get("agent_v2", mock[key]["agent"]),
                }
            )

    if not query:
        return jsonify({"error": "query or scenario_id required"}), 400

    if simulate and scenario_id:
        mock = _load_mock()
        key = str(scenario_id)
        if key in mock:
            return jsonify(
                {
                    "query": query,
                    "simulate": True,
                    **{
                        k: mock[key][k if k != "agent_v2" else "agent"]
                        for k in ("baseline", "tool_aware", "agent", "agent_v2")
                    },
                }
            )

    try:
        from src.core.factory import get_llm_provider

        llm = get_llm_provider()
    except ValueError as exc:
        return jsonify({"error": str(exc), "hint": "Use simulate mode or set API keys in .env"}), 503

    return jsonify(
        {
            "query": query,
            "simulate": False,
            "baseline": _run_mode("baseline", query, llm),
            "tool_aware": _run_mode("tool_aware", query, llm),
            "agent": _run_mode("agent", query, llm),
            "agent_v2": _run_mode("agent_v2", query, llm),
        }
    )


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
