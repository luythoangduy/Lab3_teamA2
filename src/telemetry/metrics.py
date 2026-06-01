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


def estimate_cost_usd(model: str, usage: Dict[str, int]) -> float:
    """Public helper for cost estimates (USD)."""
    return PerformanceTracker()._calculate_cost(model, usage)


def build_run_metrics(
    provider: str,
    model: str,
    usage: Dict[str, int],
    latency_ms: int,
    llm_calls: int = 1,
    simulated: bool = False,
) -> Dict[str, Any]:
    """Standard metrics block returned by chatbot/agent runs and shown in the web UI."""
    prompt_tokens = int(usage.get("prompt_tokens", 0))
    completion_tokens = int(usage.get("completion_tokens", 0))
    total_tokens = int(usage.get("total_tokens", 0) or prompt_tokens + completion_tokens)
    normalized_usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    cost_usd = estimate_cost_usd(model, normalized_usage)
    return {
        "provider": provider,
        "model": model,
        "llm_calls": llm_calls,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "latency_ms": int(latency_ms),
        "cost_usd": round(cost_usd, 6),
        "simulated": simulated,
    }


def build_comparison_evaluation(mode_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate token/cost totals across baseline → agent_v2 for one scenario run."""
    rows = []
    total_tokens = 0
    total_cost = 0.0
    total_latency = 0
    total_llm_calls = 0

    for mode, result in mode_results.items():
        metrics = (result or {}).get("metrics") or {}
        rows.append({"mode": mode, **metrics})
        total_tokens += int(metrics.get("total_tokens", 0))
        total_cost += float(metrics.get("cost_usd", 0))
        total_latency += int(metrics.get("latency_ms", 0))
        total_llm_calls += int(metrics.get("llm_calls", 0))

    simulated = bool(rows) and all(r.get("simulated", False) for r in rows)

    return {
        "simulated": simulated,
        "per_mode": rows,
        "totals": {
            "llm_calls": total_llm_calls,
            "total_tokens": total_tokens,
            "latency_ms": total_latency,
            "cost_usd": round(total_cost, 6),
        },
    }


# Global tracker instance
tracker = PerformanceTracker()

