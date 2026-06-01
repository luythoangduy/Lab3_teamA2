#!/usr/bin/env python3
"""
Side-by-side demo: Baseline Chatbot vs Tool-Aware Chatbot vs ReAct Agent
on dummyjson.com product catalog scenarios (including hallucination cases).

Usage:
  python demo_compare.py                    # all scenarios
  python demo_compare.py --scenario 1       # single scenario
  python demo_compare.py --refresh-cache    # download products to data/
  python demo_compare.py --provider openai  # override DEFAULT_PROVIDER
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

from src.agent.agent import ReActAgent
from src.chatbot.baseline import BaselineChatbot
from src.chatbot.tool_aware import ToolAwareChatbot
from src.core.factory import get_llm_provider
from src.demo.scenarios import SCENARIOS
from src.tools import refresh_cache


def print_block(title: str, result: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")
    print(f"Mode: {result.get('mode')} | Tools executed: {result.get('used_tools')} | Steps: {result.get('steps')}")
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


def run_scenario(llm, scenario: dict) -> None:
    print(f"\n\n{'#' * 60}")
    print(f"SCENARIO {scenario['id']}: {scenario['name']}")
    print(f"Query: {scenario['query']}")
    print(f"Expected: {scenario['expect']}")
    print("#" * 60)

    baseline = BaselineChatbot(llm)
    tool_chat = ToolAwareChatbot(llm)
    agent = ReActAgent(llm, max_steps=5)

    print_block("1) BASELINE CHATBOT (no tools)", baseline.run(scenario["query"]))
    print_block("2) TOOL-AWARE CHATBOT (tools in prompt, not executed)", tool_chat.run(scenario["query"]))
    print_block("3) REACT AGENT (real tool loop)", agent.run(scenario["query"]))


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Compare chatbot vs agent on product catalog")
    parser.add_argument("--scenario", type=int, help="Run one scenario id (1-4)")
    parser.add_argument("--refresh-cache", action="store_true", help="Cache dummyjson products locally")
    parser.add_argument("--provider", type=str, help="openai | google | local")
    parser.add_argument("--model", type=str)
    args = parser.parse_args()

    if args.refresh_cache:
        print(refresh_cache())
        if not args.scenario and not os.getenv("OPENAI_API_KEY") and not os.getenv("GEMINI_API_KEY"):
            return

    try:
        llm = get_llm_provider(provider=args.provider, model=args.model)
    except ValueError as exc:
        print(f"Cannot load LLM: {exc}")
        print("Copy .env.example to .env and set OPENAI_API_KEY or GEMINI_API_KEY.")
        sys.exit(1)

    scenarios = SCENARIOS
    if args.scenario:
        scenarios = [s for s in SCENARIOS if s["id"] == args.scenario]
        if not scenarios:
            print(f"No scenario with id {args.scenario}")
            sys.exit(1)

    print(f"Provider: {llm.model_name} | Scenarios: {len(scenarios)}")
    for scenario in scenarios:
        run_scenario(llm, scenario)

    print("\n\nDone. Check logs/ for JSON telemetry (HALLUCINATION_ERROR, PARSE_ERROR, LLM_METRIC).")


if __name__ == "__main__":
    main()
