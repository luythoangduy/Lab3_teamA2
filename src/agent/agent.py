import re
from typing import List, Dict, Any
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger

class ReActAgent:
    """
    A ReAct-style Agent that follows the Thought-Action-Observation loop.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []

    def get_system_prompt(self) -> str:
        """Build the system prompt with available tools and ReAct instructions."""
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        return f"""
        You are an intelligent shopping assistant that can chat naturally and use tools when product data is needed.
        You have access to the following tools:
        {tool_descriptions}

        If the user asks about products, prices, categories, recommendations, product images, or heuristic ideas
        such as "looks young", "bright color", or "garment for woman", use a product tool.
        Product results must include Markdown image syntax when the tool returns it.
        Never show more than 5 products.

        Use exactly this format when you need a tool:
        Thought: your line of reasoning.
        Action: tool_name({{"query": "text", "limit": 5}})

        After an Observation, either call another tool or answer:
        Final Answer: your final response.

        If no tool is needed, answer directly with:
        Final Answer: your final response.
        """

    def run(self, user_input: str) -> str:
        """Run the ReAct loop until the model returns a final answer."""
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})
        
        transcript = f"User: {user_input}"
        steps = 0

        while steps < self.max_steps:
            result = self.llm.generate(transcript, system_prompt=self.get_system_prompt())
            content = result.get("content", "").strip()
            logger.log_event("AGENT_LLM_RESPONSE", {"step": steps + 1, "content": content})

            final_answer = self._parse_final_answer(content)
            if final_answer:
                logger.log_event("AGENT_END", {"steps": steps + 1})
                self.history.append({"user": user_input, "assistant": final_answer})
                return final_answer

            action = self._parse_action(content)
            if not action:
                logger.log_event("AGENT_END", {"steps": steps + 1, "fallback": "no_action"})
                self.history.append({"user": user_input, "assistant": content})
                return content

            tool_name, args = action
            observation = self._execute_tool(tool_name, args)
            logger.log_event(
                "AGENT_TOOL_OBSERVATION",
                {"step": steps + 1, "tool": tool_name, "args": args, "observation": observation},
            )
            transcript = f"{transcript}\n\nAssistant:\n{content}\nObservation: {observation}"
            steps += 1
            
        logger.log_event("AGENT_END", {"steps": steps})
        return "Toi chua the hoan thanh yeu cau trong gioi han buoc cua agent."

    def _execute_tool(self, tool_name: str, args: str) -> str:
        """
        Helper method to execute tools by name.
        """
        for tool in self.tools:
            if tool['name'] == tool_name:
                tool_fn = tool.get("function")
                if not callable(tool_fn):
                    return f"Tool {tool_name} has no callable function."
                try:
                    return str(tool_fn(args))
                except Exception as exc:
                    logger.log_event("AGENT_TOOL_ERROR", {"tool": tool_name, "error": str(exc)})
                    return f"Tool {tool_name} failed: {exc}"
        return f"Tool {tool_name} not found."

    @staticmethod
    def _parse_action(content: str) -> tuple[str, str] | None:
        match = re.search(r"Action:\s*([a-zA-Z_][\w]*)\s*\((.*)\)\s*$", content, re.DOTALL)
        if not match:
            return None
        return match.group(1), match.group(2).strip()

    @staticmethod
    def _parse_final_answer(content: str) -> str | None:
        match = re.search(r"Final Answer:\s*(.*)", content, re.DOTALL)
        if not match:
            return None
        return match.group(1).strip()
