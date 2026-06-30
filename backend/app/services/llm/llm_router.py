from app.core.config import get_settings
from app.services.llm.deepseek_client import DeepSeekClient
from app.services.llm.ollama_client import OllamaClient


def get_llm_client():
    settings = get_settings()
    if settings.llm_provider == "ollama":
        return OllamaClient()
    if settings.llm_provider == "deepseek" and settings.deepseek_api_key_value:
        return DeepSeekClient()
    return None
