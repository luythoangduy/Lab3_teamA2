import time
from typing import Dict, Any, List
from src.telemetry.logger import logger

class PerformanceTracker:
    """
    Tracking industry-standard metrics for LLMs.
    """
    def __init__(self):
        self.session_metrics = []

    def track_request(self, provider: str, model: str, usage: Dict[str, int], latency_ms: int):
        """
        Logs a single request metric to our telemetry.
        """
        metric = {
            "provider": provider,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": latency_ms,
            "cost_estimate": self._calculate_cost(model, usage) # Mock cost calculation
        }
        self.session_metrics.append(metric)
        logger.log_event("LLM_METRIC", metric)

    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """
        Calculates real API costs based on model pricing per 1M tokens.
        - gpt-4o-mini: Input $0.15/1M, Output $0.60/1M
        - gpt-4o: Input $2.50/1M, Output $10.00/1M
        - gemini-1.5-flash: Input $0.075/1M, Output $0.30/1M
        - local/others: free or default basic pricing
        """
        model_lower = model.lower()
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        if "gpt-4o-mini" in model_lower:
            input_cost = (prompt_tokens / 1_000_000) * 0.15
            output_cost = (completion_tokens / 1_000_000) * 0.60
        elif "gpt-4o" in model_lower:
            input_cost = (prompt_tokens / 1_000_000) * 2.50
            output_cost = (completion_tokens / 1_000_000) * 10.00
        elif "gemini" in model_lower or "google" in model_lower:
            input_cost = (prompt_tokens / 1_000_000) * 0.075
            output_cost = (completion_tokens / 1_000_000) * 0.30
        elif "local" in model_lower:
            return 0.0
        else:
            # Default fallback pricing (similar to gpt-4o-mini)
            input_cost = (prompt_tokens / 1_000_000) * 0.15
            output_cost = (completion_tokens / 1_000_000) * 0.60

        return input_cost + output_cost

# Global tracker instance
tracker = PerformanceTracker()

