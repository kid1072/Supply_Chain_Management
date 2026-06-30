from fastapi import APIRouter

from app.core.config import get_settings
from app.core.response import success_response
from app.services.llm.llm_router import get_llm_client

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/status")
def llm_status():
    settings = get_settings()
    client = get_llm_client()
    if settings.llm_provider == "deepseek":
        return success_response(
            {
                "provider": "deepseek",
                "model": settings.deepseek_model,
                "available": client is not None,
                "base_url": settings.deepseek_base_url,
                "key_configured": bool(settings.deepseek_api_key_value),
            }
        )
    if settings.llm_provider == "ollama":
        return success_response(
            {
                "provider": "ollama",
                "model": settings.ollama_model,
                "available": client is not None,
                "base_url": settings.ollama_base_url,
            }
        )
    return success_response({"provider": "rule", "model": None, "available": True, "base_url": None})
