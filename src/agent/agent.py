import re
from typing import Any, Dict, List, Optional

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker
from src.tools.product_tools import PRODUCT_TOOLS


class ReActAgent:
    """Shopping ReAct agent backed by the product tools from the duyhk branch."""

    def __init__(
        self,
        llm: LLMProvider,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_steps: int = 5,
    ):
        self.llm = llm
        self.tools = tools or PRODUCT_TOOLS
        self.max_steps = max_steps
        self.history: List[Dict[str, str]] = []

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        return f"""
You are an intelligent shopping assistant that can chat naturally and use tools when product data is needed.
You have access to the following tools:
{tool_descriptions}

If the user asks about products, prices, categories, recommendations, product images, SQL queries, or heuristic ideas
such as "looks young", "bright color", or "garment for woman", use a product tool.
Product results must include Markdown image syntax when the tool returns it.
Never show more than 5 products.

Use exactly this format when you need a tool:
Thought: your line of reasoning.
Action: tool_name({{"query": "text", "limit": 5}})

For SQL:
Action: query_products_sql({{"sql": "SELECT * FROM products LIMIT 5", "limit": 5}})

After an Observation, either call another tool or answer:
Final Answer: your final response.

If no tool is needed, answer directly with:
Final Answer: your final response.
"""

    def run(self, user_input: str) -> Dict[str, Any]:
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})

        transcript = f"User: {user_input}"
        trace: List[Dict[str, str]] = []
        steps = 0
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        total_latency = 0
        final_answer = None
        provider = "unknown"

        while steps < self.max_steps:
            result = self.llm.generate(transcript, system_prompt=self.get_system_prompt())
            content = result.get("content", "").strip()
            provider = result.get("provider", provider)
            total_latency += result.get("latency_ms", 0)
            for key in total_usage:
                total_usage[key] += result.get("usage", {}).get(key, 0)
            logger.log_event("AGENT_LLM_RESPONSE", {"step": steps + 1, "content": content})

            thought = self._extract_thought(content)
            if thought:
                trace.append({"type": "thought", "content": thought})

            final = self._parse_final_answer(content)
            if final:
                final_answer = final
                trace.append({"type": "final_answer", "content": final_answer})
                break

            action = self._parse_action(content)
            if not action:
                err = "Could not parse Action or Final Answer. Use the required format."
                trace.append({"type": "parse_error", "content": content[:500]})
                transcript = f"{transcript}\n\nAssistant:\n{content}\nObservation: {err}"
                logger.log_event("PARSE_ERROR", {"raw": content[:300]})
                steps += 1
                continue

            tool_name, args = action
            trace.append({"type": "action", "content": f"{tool_name}({args})"})
            observation = self._execute_tool(tool_name, args)
            trace.append({"type": "observation", "content": observation})
            logger.log_event(
                "AGENT_TOOL_OBSERVATION",
                {"step": steps + 1, "tool": tool_name, "args": args, "observation": observation},
            )
            transcript = f"{transcript}\n\nAssistant:\n{content}\nObservation: {observation}"
            steps += 1

        if final_answer is None:
            final_answer = "Toi chua the hoan thanh yeu cau trong gioi han buoc cua agent."
            logger.log_event("TIMEOUT", {"steps": steps})

        tracker.track_request(provider, self.llm.model_name, total_usage, total_latency)
        logger.log_event("AGENT_END", {"steps": steps, "success": final_answer is not None})
        self.history.append({"user": user_input, "assistant": final_answer})
        return {
            "answer": final_answer,
            "mode": "react_agent",
            "used_tools": any(item["type"] == "action" for item in trace),
            "steps": steps,
            "trace": trace,
        }

    def _execute_tool(self, tool_name: str, args: str) -> str:
        for tool in self.tools:
            if tool["name"] == tool_name:
                tool_fn = tool.get("function") or tool.get("func")
                if not callable(tool_fn):
                    return f"Tool {tool_name} has no callable function."
                try:
                    return str(tool_fn(args))
                except Exception as exc:
                    logger.log_event("AGENT_TOOL_ERROR", {"tool": tool_name, "error": str(exc)})
                    return f"Tool {tool_name} failed: {exc}"
        return f"Tool {tool_name} not found."

    @staticmethod
    def _parse_action(content: str) -> Optional[tuple[str, str]]:
        match = re.search(r"Action:\s*([a-zA-Z_][\w]*)\s*\((.*)\)\s*$", content, re.DOTALL)
        if not match:
            return None
        return match.group(1), match.group(2).strip()

    @staticmethod
    def _parse_final_answer(content: str) -> Optional[str]:
        match = re.search(r"Final Answer:\s*(.*)", content, re.DOTALL)
        if not match:
            return None
        return match.group(1).strip()

    @staticmethod
    def _extract_thought(content: str) -> Optional[str]:
        match = re.search(r"Thought:\s*(.*?)(?=\n(?:Action|Final Answer|Observation):|\Z)", content, re.DOTALL)
        if not match:
            return None
        return match.group(1).strip()
