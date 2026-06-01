#!/usr/bin/env python3
"""
Side-by-side demo: Baseline Chatbot vs Tool-Aware Chatbot vs ReAct Agent
on dummyjson.com product catalog scenarios (including hallucination cases).

Usage:
  python demo_compare.py                    # all scenarios (live LLM)
  python demo_compare.py --simulate         # token/cost from mock estimates
  python demo_compare.py --scenario 1       # single scenario
  python demo_compare.py --refresh-cache    # download products to data/
  python demo_compare.py --provider openai  # override DEFAULT_PROVIDER
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

from src.agent.agent import ReActAgent
from src.agent.agent_v2 import ReActAgentV2
from src.chatbot.baseline import BaselineChatbot
from src.chatbot.tool_aware import ToolAwareChatbot
from src.core.factory import get_llm_provider
from src.demo.mock_metrics import enrich_mock_entry, mock_metrics_for_mode
from src.demo.scenarios import SCENARIOS
from src.telemetry.metrics import build_comparison_evaluation
from src.tools import refresh_cache


def _format_metrics(metrics: dict) -> str:
    if not metrics:
        return "  (no metrics)"
    sim = " [simulate]" if metrics.get("simulated") else ""
    return (
        f"  LLM calls: {metrics.get('llm_calls', 0)}{sim}\n"
        f"  Tokens: prompt={metrics.get('prompt_tokens', 0)} "
        f"completion={metrics.get('completion_tokens', 0)} "
        f"total={metrics.get('total_tokens', 0)}\n"
        f"  Latency: {metrics.get('latency_ms', 0)} ms\n"
        f"  Est. cost: ${metrics.get('cost_usd', 0):.6f} USD"
    )


def print_block(title: str, result: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")
    print(f"Mode: {result.get('mode')} | Tools executed: {result.get('used_tools')} | Steps: {result.get('steps')}")
    print(_format_metrics(result.get("metrics")))
    if result.get("note"):
        print(f"Note: {result['note']}")
    print(f"\nAnswer:\n{result.get('answer', '')[:1200]}")
    trace = result.get("trace") or []
    if trace:
        print("\nTrace:")
        for step in trace:
            kind = step["type"].upper()
            body = step["content"]
            if len(body) > 400:
                body = body[:400] + "..."
            print(f"  [{kind}] {body}")


def print_evaluation_summary(evaluation: dict, simulate: bool) -> None:
    if not evaluation:
        return
    t = evaluation.get("totals", {})
    label = "SIMULATED" if simulate or evaluation.get("simulated") else "LIVE"
    print(f"\n{'=' * 60}")
    print(f"  TOKEN & COST EVALUATION ({label})")
    print(f"{'=' * 60}")
    print(
        f"Totals: {t.get('llm_calls', 0)} calls | "
        f"{t.get('total_tokens', 0)} tokens | "
        f"{t.get('latency_ms', 0)} ms | "
        f"${t.get('cost_usd', 0):.6f} USD"
    )
    for row in evaluation.get("per_mode", []):
        print(
            f"  {row.get('mode', '?'):12} "
            f"calls={row.get('llm_calls', 0):2} "
            f"tokens={row.get('total_tokens', 0):5} "
            f"latency={row.get('latency_ms', 0):5}ms "
            f"cost=${row.get('cost_usd', 0):.6f}"
        )


def _mock_mode_result(entry: dict, mode: str, scenario_id: int) -> dict:
    base = dict(entry.get(mode, {}))
    base.setdefault("metrics", mock_metrics_for_mode(mode, scenario_id))
    return base


def run_scenario_live(llm, scenario: dict) -> None:
    query = scenario["query"]
    baseline = BaselineChatbot(llm).run(query)
    tool_chat = ToolAwareChatbot(llm).run(query)
    agent_v1 = ReActAgent(llm, max_steps=5).run(query)
    agent_v2 = ReActAgentV2(llm, max_steps=6).run(query)
    modes = {
        "baseline": baseline,
        "tool_aware": tool_chat,
        "agent": agent_v1,
        "agent_v2": agent_v2,
    }
    evaluation = build_comparison_evaluation(modes)

    print_block("1) BASELINE CHATBOT (no tools)", baseline)
    print_block("2) TOOL-AWARE CHATBOT (tools in prompt, not executed)", tool_chat)
    print_block("3) REACT AGENT v1", agent_v1)
    print_block("4) REACT AGENT v2 (images + failure guards)", agent_v2)
    print_evaluation_summary(evaluation, simulate=False)


def run_scenario_simulate(scenario: dict) -> None:
    import json

    mock_path = os.path.join(os.path.dirname(__file__), "web", "mock_traces.json")
    with open(mock_path, encoding="utf-8") as f:
        mock = json.load(f)
    entry = enrich_mock_entry(dict(mock[str(scenario["id"])]), str(scenario["id"]))
    sid = scenario["id"]

    baseline = _mock_mode_result(entry, "baseline", sid)
    tool_chat = _mock_mode_result(entry, "tool_aware", sid)
    agent_v1 = _mock_mode_result(entry, "agent", sid)
    agent_v2 = _mock_mode_result(entry, "agent_v2", sid) or _mock_mode_result(entry, "agent", sid)
    modes = {
        "baseline": baseline,
        "tool_aware": tool_chat,
        "agent": agent_v1,
        "agent_v2": agent_v2,
    }
    evaluation = build_comparison_evaluation(modes)

    print_block("1) BASELINE CHATBOT (no tools)", baseline)
    print_block("2) TOOL-AWARE CHATBOT (tools in prompt, not executed)", tool_chat)
    print_block("3) REACT AGENT v1", agent_v1)
    print_block("4) REACT AGENT v2 (images + failure guards)", agent_v2)
    print_evaluation_summary(evaluation, simulate=True)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Compare chatbot vs agent on product catalog")
    parser.add_argument("--scenario", type=int, help="Run one scenario id (1-4)")
    parser.add_argument("--refresh-cache", action="store_true", help="Cache dummyjson products locally")
    parser.add_argument("--simulate", action="store_true", help="Use mock token/cost estimates (no API)")
    parser.add_argument("--provider", type=str, help="openai | google | local")
    parser.add_argument("--model", type=str)
    args = parser.parse_args()

    if args.refresh_cache:
        print(refresh_cache())
        if args.simulate and not args.scenario:
            return

    scenarios = SCENARIOS
    if args.scenario:
        scenarios = [s for s in SCENARIOS if s["id"] == args.scenario]
        if not scenarios:
            print(f"No scenario with id {args.scenario}")
            sys.exit(1)

    if args.simulate:
        print(f"Mode: SIMULATE | Scenarios: {len(scenarios)}")
        for scenario in scenarios:
            run_scenario_simulate(scenario)
    else:
        try:
            llm = get_llm_provider(provider=args.provider, model=args.model)
        except ValueError as exc:
            print(f"Cannot load LLM: {exc}")
            print("Copy .env.example to .env, or use --simulate for mock metrics.")
            sys.exit(1)
        print(f"Provider: {llm.model_name} | Scenarios: {len(scenarios)}")
        for scenario in scenarios:
            run_scenario_live(llm, scenario)

    print("\n\nDone. Check logs/ for LLM_METRIC events.")


if __name__ == "__main__":
    main()
