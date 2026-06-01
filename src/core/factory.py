import os
from typing import Optional

from dotenv import load_dotenv

from src.core.gemini_provider import GeminiProvider
from src.core.llm_provider import LLMProvider
from src.core.openai_provider import OpenAIProvider


def get_llm_provider(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMProvider:
    load_dotenv()
    provider = (provider or os.getenv("DEFAULT_PROVIDER", "openai")).lower()
    model = model or os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

    if provider == "openai":
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY missing in .env")
        return OpenAIProvider(model_name=model, api_key=key)

    if provider in ("google", "gemini"):
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY missing in .env")
        gemini_model = os.getenv("GOOGLE_GEMINI_MODEL") or os.getenv("GEMINI_MODEL") or model or "gemini-1.5-flash"
        return GeminiProvider(model_name=gemini_model, api_key=key)

    if provider == "local":
        from src.core.local_provider import LocalProvider

        path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        return LocalProvider(model_path=path)

    raise ValueError(f"Unknown provider: {provider}")
