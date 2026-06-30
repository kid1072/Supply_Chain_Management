from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.recommendation import AIRecommendation
from app.services.llm.deepseek_client import DeepSeekClient
from app.services.llm.llm_router import get_llm_client
from app.services.llm.ollama_client import OllamaClient
from app.services.recommendation_service import generate_recommendations


def test_llm_router_rule(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "rule")
    get_settings.cache_clear()
    assert get_llm_client() is None


def test_llm_router_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()
    assert isinstance(get_llm_client(), OllamaClient)


def test_llm_router_deepseek(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "masked")
    get_settings.cache_clear()
    assert isinstance(get_llm_client(), DeepSeekClient)


def test_recommendations_deepseek_invalid_key_falls_back(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "invalid")
    get_settings.cache_clear()

    def fail_fast(self, prompt: str):
        raise RuntimeError("invalid key")

    monkeypatch.setattr(DeepSeekClient, "generate_text", fail_fast)

    session = SessionLocal()
    try:
        items = generate_recommendations(session)
        session.commit()
        assert len(items) > 0
        high_risk = session.query(AIRecommendation).filter_by(risk_level="high").all()
        assert high_risk
        assert all(item.llm_provider == "rule" and item.llm_used is False for item in high_risk)
    finally:
        session.close()


def test_recommendations_high_risk_use_llm_by_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "masked")
    get_settings.cache_clear()

    monkeypatch.setattr(DeepSeekClient, "generate_text", lambda self, prompt: f"enhanced::{prompt[:20]}")

    session = SessionLocal()
    try:
        items = generate_recommendations(session)
        session.commit()
        assert len(items) > 0
        high_risk = session.query(AIRecommendation).filter_by(risk_level="high").all()
        assert high_risk
        assert all(item.llm_used is True and item.reason_enhanced for item in high_risk)
        non_high_risk = session.query(AIRecommendation).filter(AIRecommendation.risk_level != "high").all()
        assert all(item.llm_used is False and item.reason_enhanced is None for item in non_high_risk)
    finally:
        session.close()
