from app.core.config import get_settings
from app.services.llm.base import ModelProvider
from app.services.llm.mock import MockModelProvider
from app.services.llm.openai_compatible import OpenAICompatibleProvider


def get_model_provider() -> ModelProvider:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockModelProvider()
    if settings.llm_provider in {"openai_compatible", "ark", "doubao"}:
        return OpenAICompatibleProvider(settings)
    raise ValueError(f"不支持的模型提供商：{settings.llm_provider}")
