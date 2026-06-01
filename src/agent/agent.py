import re
from typing import Any, Dict, List, Optional

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker
from src.tools.product_tools import PRODUCT_TOOLS, execute_tool


class ReActAgent:
    """ReAct agent: Thought -> Action -> Observation loop with real tool execution."""

    def __init__(
        self,
        llm: LLMProvider,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_steps: int = 5,
    ):
        self.llm = llm
        self.tools = tools or PRODUCT_TOOLS
        self.max_steps = max_steps
        self.history: List[str] = []

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join(
            f"- {t['name']}: {t['description']}" for t in self.tools
        )
        return f"""You are a product catalog assistant. Data comes ONLY from tools — never invent prices or stock.

Available tools:
{tool_descriptions}

Respond using EXACTLY this format (one block per turn):
Thought: brief reasoning
Action: tool_name(argument)
OR when done:
Thought: brief reasoning
Final Answer: concise answer for the user

Rules:
- Use tool_name(argument) with a single string or integer argument in parentheses.
- After you write Action, stop and wait for Observation (do not invent observations).
- If a product is not in the catalog, say so in Final Answer.
- For multi-step questions, call tools one at a time."""

    def run(self, user_input: str) -> Dict[str, Any]:
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})

        scratchpad = f"Question: {user_input}\n"
        trace: List[Dict[str, str]] = []
        steps = 0
        final_answer = None
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        total_latency = 0

        while steps < self.max_steps:
            prompt = scratchpad + "\nWhat is your next step?"
            result = self.llm.generate(prompt, system_prompt=self.get_system_prompt())
            content = result.get("content", "")
            total_latency += result.get("latency_ms", 0)
            for key in total_usage:
                total_usage[key] += result.get("usage", {}).get(key, 0)

            thought = self._extract_line(content, "Thought")
            action = self._parse_action(content)
            final = self._extract_line(content, "Final Answer", rest_of_message=True)

            if thought:
                trace.append({"type": "thought", "content": thought})
                scratchpad += f"\nThought: {thought}"

            if final:
                final_answer = final
                trace.append({"type": "final_answer", "content": final_answer})
                scratchpad += f"\nFinal Answer: {final_answer}"
                break

            if action:
                tool_name, args = action
                trace.append({"type": "action", "content": f"{tool_name}({args})"})
                scratchpad += f"\nAction: {tool_name}({args})"

                observation = execute_tool(tool_name, args)
                if "HALLUCINATED_TOOL" in observation:
                    logger.log_event("HALLUCINATION_ERROR", {"tool": tool_name})
                trace.append({"type": "observation", "content": observation})
                scratchpad += f"\nObservation: {observation}"
            else:
                # Unparseable output — nudge model
                err = "Could not parse Action or Final Answer. Use the required format."
                trace.append({"type": "parse_error", "content": content[:500]})
                scratchpad += f"\nObservation: {err}"
                logger.log_event("PARSE_ERROR", {"raw": content[:300]})

            steps += 1

        if final_answer is None:
            final_answer = (
                "I could not finish within the step limit. "
                "See trace in logs for partial reasoning."
            )
            logger.log_event("TIMEOUT", {"steps": steps})

        tracker.track_request(
            result.get("provider", "unknown") if steps else "unknown",
            self.llm.model_name,
            total_usage,
            total_latency,
        )
        logger.log_event("AGENT_END", {"steps": steps, "success": final_answer is not None})

        return {
            "answer": final_answer,
            "mode": "react_agent",
            "used_tools": any(t["type"] == "action" for t in trace),
            "steps": steps,
            "trace": trace,
        }

    @staticmethod
    def _extract_line(text: str, label: str, rest_of_message: bool = False) -> Optional[str]:
        pattern = (
            rf"{label}:\s*(.+)$"
            if rest_of_message
            else rf"{label}:\s*(.+?)(?=\n(?:Thought|Action|Final Answer|Observation):|\Z)"
        )
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else None

    @staticmethod
    def _parse_action(text: str) -> Optional[tuple]:
        match = re.search(r"Action:\s*(\w+)\(([^)]*)\)", text, re.IGNORECASE)
        if match:
            return match.group(1), match.group(2).strip()
        return None
