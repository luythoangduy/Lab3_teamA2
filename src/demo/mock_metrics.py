"""Simulated token/cost estimates for web demo (no API key)."""

from typing import Any, Dict

from src.telemetry.metrics import build_run_metrics

# Per-mode baseline estimates (gpt-4o-mini pricing via build_run_metrics)
_MODE_PROFILES: Dict[str, Dict[str, int]] = {
    "baseline": {"llm_calls": 1, "prompt_tokens": 380, "completion_tokens": 95, "latency_ms": 920},
    "tool_aware": {"llm_calls": 1, "prompt_tokens": 720, "completion_tokens": 130, "latency_ms": 1100},
    "agent": {"llm_calls": 2, "prompt_tokens": 2100, "completion_tokens": 380, "latency_ms": 3400},
    "agent_v2": {"llm_calls": 3, "prompt_tokens": 3200, "completion_tokens": 520, "latency_ms": 5100},
}

# Scenario-specific overrides (llm_calls / tokens)
_SCENARIO_OVERRIDES: Dict[str, Dict[str, Dict[str, int]]] = {
    "1": {
        "agent": {"llm_calls": 2, "prompt_tokens": 2400, "completion_tokens": 420, "latency_ms": 3800},
        "agent_v2": {"llm_calls": 3, "prompt_tokens": 3500, "completion_tokens": 480, "latency_ms": 4900},
    },
    "2": {
        "agent": {"llm_calls": 2, "prompt_tokens": 2600, "completion_tokens": 400, "latency_ms": 3600},
        "agent_v2": {"llm_calls": 4, "prompt_tokens": 4800, "completion_tokens": 650, "latency_ms": 6200},
    },
    "3": {
        "agent": {"llm_calls": 2, "prompt_tokens": 2200, "completion_tokens": 350, "latency_ms": 3200},
        "agent_v2": {"llm_calls": 2, "prompt_tokens": 2800, "completion_tokens": 400, "latency_ms": 3500},
    },
    "4": {
        "agent": {"llm_calls": 3, "prompt_tokens": 3400, "completion_tokens": 500, "latency_ms": 4800},
        "agent_v2": {"llm_calls": 3, "prompt_tokens": 3900, "completion_tokens": 550, "latency_ms": 5300},
    },
}


def mock_metrics_for_mode(mode: str, scenario_id: str) -> Dict[str, Any]:
    profile = dict(_MODE_PROFILES.get(mode, _MODE_PROFILES["baseline"]))
    overrides = _SCENARIO_OVERRIDES.get(str(scenario_id), {}).get(mode)
    if overrides:
        profile.update(overrides)
    usage = {
        "prompt_tokens": profile["prompt_tokens"],
        "completion_tokens": profile["completion_tokens"],
        "total_tokens": profile["prompt_tokens"] + profile["completion_tokens"],
    }
    return build_run_metrics(
        provider="simulate",
        model="gpt-4o-mini (mock)",
        usage=usage,
        latency_ms=profile["latency_ms"],
        llm_calls=profile["llm_calls"],
        simulated=True,
    )


def enrich_mock_entry(entry: Dict[str, Any], scenario_id: str) -> Dict[str, Any]:
    for mode in ("baseline", "tool_aware", "agent", "agent_v2"):
        if mode not in entry:
            continue
        if not entry[mode].get("metrics"):
            entry[mode]["metrics"] = mock_metrics_for_mode(mode, scenario_id)
    return entry
