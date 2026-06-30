from typing import Any

import requests

from app.core.config import get_settings
from app.services.llm.base import BaseLLMClient


class DeepSeekClient(BaseLLMClient):
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_text(self, prompt: str) -> str:
        response = requests.post(
            f"{self.settings.deepseek_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.deepseek_api_key_value}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.deepseek_model,
                "messages": [
                    {"role": "system", "content": "你是一个供应链库存补货分析助手。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=self.settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def generate_json(self, prompt: str, json_schema: dict | None = None) -> dict[str, Any]:
        return {"text": self.generate_text(prompt), "json_schema": json_schema or {}}
