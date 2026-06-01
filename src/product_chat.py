import os

from dotenv import load_dotenv

from src.agent.agent import ReActAgent
from src.tools.product_tools import create_product_tools


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


def main() -> None:
    agent = ReActAgent(llm=build_provider(), tools=create_product_tools(), max_steps=5)
    print("Product agent ready. Type 'exit' to quit.")
    while True:
        user_input = input("\nUser: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        print(f"\nAssistant:\n{agent.run(user_input)}")


if __name__ == "__main__":
    main()
