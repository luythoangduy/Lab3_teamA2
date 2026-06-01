import os

from dotenv import load_dotenv

from src.agent.agent import ReActAgent
from src.agent.agent_v2 import ReActAgentV2
from src.tools.product_tools import create_product_tools
from src.telemetry.metrics import tracker


def build_provider():
    load_dotenv()
    provider = os.getenv("DEFAULT_PROVIDER", "openai").lower()
    model_name = os.getenv("DEFAULT_MODEL", "gpt-4o")

    if provider in {"google", "gemini"}:
        from src.core.gemini_provider import GeminiProvider

        return GeminiProvider(
            model_name=os.getenv("GOOGLE_GEMINI_MODEL") or os.getenv("GEMINI_MODEL") or model_name or "gemini-1.5-flash",
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        )
    if provider == "local":
        from src.core.local_provider import LocalProvider

        return LocalProvider(model_path=os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf"))
    from src.core.openai_provider import OpenAIProvider

    return OpenAIProvider(model_name=model_name, api_key=os.getenv("OPENAI_API_KEY"))


def build_agent():
    llm = build_provider()
    tools = create_product_tools()
    if os.getenv("AGENT_VERSION", "v2").lower() == "v1":
        return ReActAgent(llm=llm, tools=tools, max_steps=5)
    return ReActAgentV2(llm=llm, tools=tools, max_steps=6)


def main() -> None:
    agent = build_agent()
    version = os.getenv("AGENT_VERSION", "v2")
    print(f"Product agent ready ({version}). Type 'exit' to quit.")
    while True:
        user_input = input("\nUser: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        result = agent.run(user_input)
        answer = result.get("answer", result) if isinstance(result, dict) else result
        print(f"\nAssistant:\n{answer}")
        if tracker.session_metrics:
            last = tracker.session_metrics[-1]
            cost = last.get("cost_estimate", 0.0)
            t_tok = last.get("total_tokens", 0)
            p_tok = last.get("prompt_tokens", 0)
            c_tok = last.get("completion_tokens", 0)
            lat = last.get("latency_ms", 0)
            print(f"\n💡 [Metrics] Latency: {lat}ms | Cost: ${cost:.6f} USD | Tokens: {t_tok} (Prompt: {p_tok}, Completion: {c_tok})")
        if isinstance(result, dict) and result.get("failures"):
            print(f"\n[Failures detected: {len(result['failures'])} — see logs/]")


if __name__ == "__main__":
    main()
