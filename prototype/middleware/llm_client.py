"""HTTP-клиент к llama-server.

llama.cpp поддерживает OpenAI-совместимый API: POST /v1/chat/completions.
Шаг 3 добавит /steering endpoint для control vectors.
"""

from typing import List, Dict, Any, Optional

import httpx


class LlamaServerClient:
    def __init__(self, base_url: str = "http://localhost:8080", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 200,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
        slot_id: Optional[int] = None,
        cache_prompt: Optional[bool] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if model is not None:
            payload["model"] = model
        if stop:
            payload["stop"] = stop
        # llama.cpp-специфичные параметры — Ollama их игнорирует
        if slot_id is not None:
            payload["id_slot"] = slot_id
        if cache_prompt is not None:
            payload["cache_prompt"] = cache_prompt

        url = f"{self.base_url}/v1/chat/completions"
        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def health(self) -> bool:
        """Универсальный health-check: пробуем эндпоинты llama.cpp и Ollama."""
        for path in ("/health", "/api/tags", "/v1/models"):
            try:
                resp = await self.client.get(f"{self.base_url}{path}", timeout=5.0)
                if resp.status_code == 200:
                    return True
            except Exception:
                continue
        return False

    async def slot_save(self, slot_id: int, filename: str) -> bool:
        """Сохранение KV-cache слота на диск (для persistence характера)."""
        url = f"{self.base_url}/slots/{slot_id}?action=save"
        resp = await self.client.post(url, json={"filename": filename})
        return resp.status_code == 200

    async def slot_restore(self, slot_id: int, filename: str) -> bool:
        url = f"{self.base_url}/slots/{slot_id}?action=restore"
        resp = await self.client.post(url, json={"filename": filename})
        return resp.status_code == 200

    async def close(self) -> None:
        await self.client.aclose()
