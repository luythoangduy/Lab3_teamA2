"""Load or build evaluation metrics for live runs and simulate mode."""

import json
import os
from typing import Any, Dict

from src.telemetry.metrics import build_comparison_evaluation, build_run_metrics

MOCK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "web",
    "mock_traces.json",
)


def load_mock_scenario(scenario_id: int) -> Dict[str, Any]:
    with open(MOCK_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data[str(scenario_id)]


def attach_metrics_if_missing(result: Dict[str, Any], provider: str, model: str) -> Dict[str, Any]:
    if result.get("metrics"):
        return result
    result["metrics"] = build_run_metrics(provider, model, {}, 0, llm_calls=0, simulated=False)
    return result
