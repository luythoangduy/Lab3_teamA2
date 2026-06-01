"""Baseline chatbot: LLM only, no tool execution (prone to hallucination on catalog facts)."""
from typing import Any, Dict

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import build_run_metrics, tracker


class BaselineChatbot:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def get_system_prompt(self) -> str:
        return (
            "You are a friendly e-commerce shopping assistant for an online store "
            "with beauty, fragrances, furniture, and grocery products. "
            "Answer customer questions helpfully. "
            "If you are unsure, make your best guess based on typical e-commerce catalogs."
        )

    def run(self, user_input: str) -> Dict[str, Any]:
        logger.log_event("CHATBOT_START", {"input": user_input, "mode": "baseline_no_tools"})
        result = self.llm.generate(user_input, system_prompt=self.get_system_prompt())
        tracker.track_request(
            result.get("provider", "unknown"),
            self.llm.model_name,
            result.get("usage", {}),
            result.get("latency_ms", 0),
        )
        logger.log_event("CHATBOT_END", {"mode": "baseline_no_tools"})
        metrics = build_run_metrics(
            result.get("provider", "unknown"),
            self.llm.model_name,
            result.get("usage", {}),
            result.get("latency_ms", 0),
            llm_calls=1,
        )
        return {
            "answer": result["content"],
            "mode": "baseline",
            "used_tools": False,
            "steps": 1,
            "trace": [],
            "metrics": metrics,
        }
