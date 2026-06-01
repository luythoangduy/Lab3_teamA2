"""
Tool-aware chatbot: tools are described in the prompt but NEVER executed.
Demonstrates hallucinated tool results vs a real ReAct agent.
"""
from typing import Any, Dict, List

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import build_run_metrics, tracker
from src.tools.product_tools import PRODUCT_TOOLS


class ToolAwareChatbot:
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]] | None = None):
        self.llm = llm
        self.tools = tools or PRODUCT_TOOLS

    def get_system_prompt(self) -> str:
        tool_lines = "\n".join(f"- {t['name']}: {t['description']}" for t in self.tools)
        return (
            "You are an e-commerce assistant with these tools:\n"
            f"{tool_lines}\n\n"
            "Explain what you would do with these tools, but do not execute them. "
            "If you mention catalog facts, make clear they are estimates from prompt context only."
        )

    def run(self, user_input: str) -> Dict[str, Any]:
        logger.log_event("CHATBOT_START", {"input": user_input, "mode": "tool_aware_no_execution"})
        result = self.llm.generate(user_input, system_prompt=self.get_system_prompt())
        tracker.track_request(
            result.get("provider", "unknown"),
            self.llm.model_name,
            result.get("usage", {}),
            result.get("latency_ms", 0),
        )
        logger.log_event("CHATBOT_END", {"mode": "tool_aware_no_execution"})
        metrics = build_run_metrics(
            result.get("provider", "unknown"),
            self.llm.model_name,
            result.get("usage", {}),
            result.get("latency_ms", 0),
            llm_calls=1,
        )
        return {
            "answer": result["content"],
            "mode": "tool_aware_chatbot",
            "used_tools": False,
            "steps": 1,
            "trace": [],
            "note": "Tools described in prompt only; no real tool execution happened",
            "metrics": metrics,
        }

