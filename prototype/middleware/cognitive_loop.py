"""Cognitive loop — основной мозг Странника.

Архитектура соответствует 05-architecture-v0.md:
- Шаг 1: только sense → think → respond. Без steering, без thought stream.
- Шаг 3: добавление persona vectors через /steering.
- Шаг 4: thought stream (П4) — divergent + convergent.
- Шаг 5: sleep consolidation (П3).
"""

import time
from typing import List, Dict, Any, Optional

from .character import CharacterState
from .llm_client import LlamaServerClient
from .memory import STM, LTM, Event, Source
from .prompts import build_system_prompt


class CognitiveAgent:
    """Один NPC. Шаг 1 — минимальный жизнеспособный мозг.

    Mindcraft присылает нам chat_completion-запрос с историей сообщений.
    Внутри мы:
      1. Извлекаем последнее восприятие (последнее user-сообщение).
      2. Записываем его в STM.
      3. Собираем system prompt из текущего state.
      4. Дёргаем llama-server.
      5. Парсим ответ → возвращаем Mindcraft в OpenAI-формате.
    """

    def __init__(
        self,
        name: str,
        character: CharacterState,
        llm: LlamaServerClient,
        model_name: str = "Sweaterdog/Andy-4",
        stm_capacity: int = 50,
        ltm_max_size: int = 1000,
    ):
        self.name = name
        self.character = character
        self.llm = llm
        self.model_name = model_name
        self.stm = STM(capacity=stm_capacity)
        self.ltm = LTM(max_size=ltm_max_size)
        self.last_perception: str = "(пока не понятно где ты)"

    def observe(self, perception_text: str, perception_type: str = "saw") -> None:
        """Восприятие → STM. Шаг 1 — простая запись.

        Шаг 2+ — selective_perception filter, affect_score через mini-LLM.
        """
        ev = Event(
            timestamp=time.time(),
            perception_type=perception_type,
            content=perception_text,
            affect_signature=(0.0, 0.0, 0.0),
        )
        self.stm.add(ev)
        self.last_perception = perception_text

    async def respond(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 200,
        temperature: float = 0.7,
    ) -> str:
        """Главный вход: Mindcraft даёт сообщение, мы возвращаем ответ.

        history — диалоговый контекст от Mindcraft (system+user+assistant).
        Мы заменяем первый system на наш собранный, оставляем диалог.
        """
        # Записываем user_message как восприятие.
        # Mindcraft в user-сообщении передаёт смесь: восприятие мира + реплику игрока.
        # На Шаге 1 — упрощённо: всё в STM как perception.
        self.observe(user_message, perception_type="saw")

        # Собираем наш system prompt — характер + STM + LTM.
        system_prompt = build_system_prompt(
            self.character,
            self.stm,
            self.ltm,
            perception_summary=user_message[:500],
        )

        # Реконструируем messages: наш system + diaлоговая история без system.
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if history:
            for m in history:
                if m.get("role") in ("user", "assistant"):
                    messages.append(m)
        messages.append({"role": "user", "content": user_message})

        result = await self.llm.chat_completion(
            messages=messages,
            model=self.model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            # slot_id и cache_prompt — только для llama.cpp; Ollama их игнорирует
        )

        # OpenAI-формат: choices[0].message.content
        choices = result.get("choices", [])
        if not choices:
            return "(Странник молчит)"
        content = choices[0].get("message", {}).get("content", "").strip()

        # Записываем собственный ответ в STM как "сказал/сделал".
        self.stm.add(Event(
            timestamp=time.time(),
            perception_type="said",
            content=content[:300],
        ))

        return content
