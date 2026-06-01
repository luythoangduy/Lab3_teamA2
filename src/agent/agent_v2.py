"""
Agent v2: ReAct loop with image preservation and failure detection / avoidance.

Improvements over v1 (for lab rubric):
- Detects: parse errors, hallucinated tools, empty catalog, empty search, duplicate actions
- Avoids: corrective observations, auto-refresh empty DB, valid-tool hints, image carry-over
- Logs structured failure codes for telemetry / group report
"""
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import build_run_metrics, tracker
from src.tools.product_tools import CATALOG, PRODUCT_TOOLS

IMAGE_MD_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")


class ReActAgentV2:
    def __init__(
        self,
        llm: LLMProvider,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_steps: int = 6,
        max_parse_retries: int = 2,
    ):
        self.llm = llm
        self.tools = tools or PRODUCT_TOOLS
        self.max_steps = max_steps
        self.max_parse_retries = max_parse_retries
        self.valid_tool_names = {t["name"] for t in self.tools}
        self.history: List[Dict[str, str]] = []

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        valid = ", ".join(sorted(self.valid_tool_names))
        return f"""You are a shopping assistant (Agent v2). Use tools for any product fact. Never invent data.

Tools:
{tool_descriptions}

Valid tool names only: {valid}

Rules:
- When tools return Markdown images ![title](url), copy those image lines into your Final Answer.
- If a tool returns no products, say clearly that nothing was found — do not invent items.
- If you see ERROR or GUARD in an Observation, follow the recovery hint before answering.

Format:
Thought: reasoning
Action: tool_name({{"query": "mascara", "limit": 5}})
Observation: (provided by system — do not write yourself)

Then either another Thought/Action or:
Final Answer: user-facing reply with images when available
"""

    def run(self, user_input: str) -> Dict[str, Any]:
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name, "version": "v2"})

        failures: List[Dict[str, str]] = []
        trace: List[Dict[str, str]] = []
        collected_images: List[str] = []
        seen_actions: Set[str] = set()
        parse_retries = 0

        transcript = f"User: {user_input}"
        steps = 0
        final_answer: Optional[str] = None
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        total_latency = 0
        llm_calls = 0
        provider = "unknown"

        if CATALOG.count() == 0:
            obs = self._auto_refresh()
            failures.append({"code": "EMPTY_CATALOG", "recovery": "auto_refresh"})
            trace.append({"type": "observation", "content": obs})

        while steps < self.max_steps:
            result = self.llm.generate(transcript, system_prompt=self.get_system_prompt())
            llm_calls += 1
            content = result.get("content", "").strip()
            provider = result.get("provider", provider)
            total_latency += result.get("latency_ms", 0)
            for key in total_usage:
                total_usage[key] += result.get("usage", {}).get(key, 0)

            if content.startswith("Gemini did not return"):
                failures.append({"code": "EMPTY_LLM_RESPONSE", "detail": content[:120]})
                transcript += f"\n\nObservation: ERROR: {content}. Reply with Final Answer only."
                steps += 1
                continue

            logger.log_event("AGENT_LLM_RESPONSE", {"step": steps + 1, "version": "v2", "content": content[:500]})

            thought = self._extract_thought(content)
            if thought:
                trace.append({"type": "thought", "content": thought})

            final = self._parse_final_answer(content)
            if final:
                final_answer = self._finalize_answer(final, collected_images, failures, trace)
                break

            action = self._parse_action(content)
            if not action:
                parse_retries += 1
                failures.append({"code": "PARSE_ERROR", "detail": content[:200]})
                trace.append({"type": "parse_error", "content": content[:500]})
                logger.log_event("PARSE_ERROR", {"raw": content[:300], "version": "v2"})
                if parse_retries > self.max_parse_retries:
                    final_answer = (
                        "I had trouble following the required Thought/Action format. "
                        "Please try rephrasing your question."
                    )
                    break
                transcript = (
                    f"{transcript}\n\nAssistant:\n{content}\n"
                    "Observation: GUARD: Use exactly 'Thought:', 'Action: tool_name({...})', or 'Final Answer:'."
                )
                steps += 1
                continue

            parse_retries = 0
            tool_name, args = action
            action_key = f"{tool_name}|{args}"
            if action_key in seen_actions:
                failures.append({"code": "DUPLICATE_ACTION", "tool": tool_name})
                trace.append({"type": "guard", "content": f"Duplicate action blocked: {tool_name}({args})"})
                logger.log_event("AGENT_GUARD", {"reason": "duplicate_action", "tool": tool_name})
                transcript = (
                    f"{transcript}\n\nAssistant:\n{content}\n"
                    "Observation: GUARD: You already ran this action. Use Final Answer or a different tool."
                )
                steps += 1
                continue
            seen_actions.add(action_key)

            trace.append({"type": "action", "content": f"{tool_name}({args})"})
            observation, failure = self._execute_with_detection(tool_name, args)
            if failure:
                failures.append(failure)
                logger.log_event(f"AGENT_{failure['code']}", failure)

            collected_images.extend(IMAGE_MD_RE.findall(observation))
            trace.append({"type": "observation", "content": observation[:2000]})

            if tool_name == "refresh_products" and (
                "Loaded" in observation or "Cached" in observation
            ):
                seen_actions.clear()

            recovery = self._recovery_observation(failure, tool_name)
            transcript = f"{transcript}\n\nAssistant:\n{content}\nObservation: {observation}"
            if recovery:
                transcript += f"\nObservation: {recovery}"
            steps += 1

        if final_answer is None:
            if collected_images:
                final_answer = (
                    "I reached the step limit before a final text answer, "
                    "but here are product images from tool results:\n\n"
                    + "\n".join(list(dict.fromkeys(collected_images))[:5])
                )
            else:
                final_answer = "I could not complete the request within the step limit."
            failures.append({"code": "TIMEOUT", "steps": str(steps)})
            trace.append({"type": "final_answer", "content": final_answer})
            logger.log_event("TIMEOUT", {"steps": steps, "version": "v2"})

        metrics = build_run_metrics(
            provider, self.llm.model_name, total_usage, total_latency, llm_calls=llm_calls
        )
        tracker.track_request(provider, self.llm.model_name, total_usage, total_latency)
        logger.log_event(
            "AGENT_END",
            {"steps": steps, "version": "v2", "failure_count": len(failures), "metrics": metrics},
        )
        self.history.append({"user": user_input, "assistant": final_answer})

        return {
            "answer": final_answer,
            "mode": "react_agent_v2",
            "used_tools": any(t["type"] == "action" for t in trace),
            "steps": steps,
            "trace": trace,
            "failures": failures,
            "images_preserved": bool(collected_images),
            "metrics": metrics,
        }

    def _execute_with_detection(self, tool_name: str, args: str) -> Tuple[str, Optional[Dict[str, str]]]:
        if tool_name not in self.valid_tool_names:
            valid = ", ".join(sorted(self.valid_tool_names))
            msg = json.dumps(
                {
                    "error": "HALLUCINATED_TOOL",
                    "message": f"Tool '{tool_name}' does not exist",
                    "valid_tools": list(self.valid_tool_names),
                }
            )
            return msg, {"code": "HALLUCINATED_TOOL", "tool": tool_name, "valid_tools": valid}

        for tool in self.tools:
            if tool["name"] != tool_name:
                continue
            fn = tool.get("function") or tool.get("func")
            if not callable(fn):
                return f"Tool {tool_name} has no callable function.", {"code": "TOOL_ERROR", "tool": tool_name}
            try:
                result = str(fn(args))
            except Exception as exc:
                logger.log_event("AGENT_TOOL_ERROR", {"tool": tool_name, "error": str(exc)})
                return f"Tool {tool_name} failed: {exc}", {"code": "TOOL_ERROR", "tool": tool_name}

            failure = self._classify_observation(result)
            return result, failure

        return (
            json.dumps({"error": "HALLUCINATED_TOOL", "message": f"Tool '{tool_name}' not found"}),
            {"code": "HALLUCINATED_TOOL", "tool": tool_name},
        )

    @staticmethod
    def _classify_observation(observation: str) -> Optional[Dict[str, str]]:
        lower = observation.lower()
        if "hallucinated_tool" in lower:
            return {"code": "HALLUCINATED_TOOL"}
        if "invalid_args" in lower or "tool_error" in lower:
            return {"code": "TOOL_ERROR"}
        if "no matching products" in lower or "khong tim thay" in lower:
            return {"code": "EMPTY_RESULT"}
        if '"error"' in lower and "not found" in lower:
            return {"code": "NOT_FOUND"}
        return None

    @staticmethod
    def _recovery_observation(failure: Optional[Dict[str, str]], tool_name: str) -> str:
        if not failure:
            return ""
        code = failure.get("code")
        if code == "HALLUCINATED_TOOL":
            return f"GUARD: Use only valid tools. Suggested: search_products or get_product_by_id. You tried '{tool_name}'."
        if code == "EMPTY_RESULT":
            return "GUARD: No products matched. Try refresh_products, a broader search_products query, or query_products_sql."
        if code == "NOT_FOUND":
            return "GUARD: Item not in catalog. Do not invent a substitute product or price."
        if code == "TOOL_ERROR":
            return "GUARD: Fix tool arguments (JSON with correct keys) or choose another tool."
        return ""

    def _finalize_answer(
        self,
        answer: str,
        images: List[str],
        failures: List[Dict[str, str]],
        trace: List[Dict[str, str]],
    ) -> str:
        unique_images = []
        for img in images:
            if img not in unique_images:
                unique_images.append(img)

        if unique_images and not IMAGE_MD_RE.search(answer):
            failures.append({"code": "MISSING_IMAGES_IN_ANSWER", "recovery": "appended_from_observations"})
            logger.log_event("AGENT_IMAGE_GUARD", {"appended": len(unique_images)})
            answer = answer.rstrip() + "\n\n" + "\n".join(unique_images[:5])

        trace.append({"type": "final_answer", "content": answer})
        return answer

    @staticmethod
    def _auto_refresh() -> str:
        try:
            count = CATALOG.refresh_from_api(limit=50)
            return f"System auto-loaded {count} products into the catalog."
        except Exception as exc:
            return f"System could not load catalog: {exc}"

    def _execute_tool(self, tool_name: str, args: str) -> str:
        obs, _ = self._execute_with_detection(tool_name, args)
        return obs

    @staticmethod
    def _parse_action(content: str) -> Optional[tuple]:
        # Prefer Action anywhere in the block (models often add text after the call)
        match = re.search(r"Action:\s*([a-zA-Z_][\w]*)\s*\((.*)\)", content, re.DOTALL | re.IGNORECASE)
        if not match:
            return None
        args = match.group(2).strip()
        # Trim trailing junk after the closing paren of JSON args
        depth = 0
        end = 0
        for i, ch in enumerate(args):
            if ch in "{[(":
                depth += 1
            elif ch in "}])":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end:
            args = args[:end]
        return match.group(1), args

    @staticmethod
    def _parse_final_answer(content: str) -> Optional[str]:
        match = re.search(r"Final Answer:\s*(.*)", content, re.DOTALL)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_thought(content: str) -> Optional[str]:
        match = re.search(
            r"Thought:\s*(.*?)(?=\n(?:Action|Final Answer|Observation):|\Z)",
            content,
            re.DOTALL,
        )
        return match.group(1).strip() if match else None
