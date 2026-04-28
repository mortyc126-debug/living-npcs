"""Cognitive loop — основной мозг Странника.

Архитектура соответствует 05-architecture-v0.md:
- Шаг 1: только sense → think → respond. Без steering, без thought stream.
- Шаг 3: добавление persona vectors через /steering.
- Шаг 4: thought stream (П4) — divergent + convergent.
- Шаг 5: sleep consolidation (П3).
"""

import re
import time
from typing import List, Dict, Any, Optional

from .character import CharacterState
from .llm_client import LlamaServerClient
from .memory import STM, LTM, Event, Source
from .mindcraft_adapter import parse_user_message, ground_action
from .prompts import build_system_prompt


# Mindcraft info-команды: их вывод возвращается боту как новый user-сообщение,
# что создаёт self-loop. Action-команды (move/mine/attack/...) трогать нельзя.
INFO_COMMANDS = {
    "!stats", "!nearbyBlocks", "!entities", "!inventory", "!modes",
    "!savedPlaces", "!viewChest", "!searchForBlock", "!searchForEntity",
    "!checkBlueprint", "!checkBlueprintLevel",
    "!getBlueprint", "!getBlueprintLevel",
    # Управление режимами/новый код — модель часто галлюцинирует
    # несуществующие моды и зацикливается на ошибках.
    # !goal вооружает self_prompter (см. patches/mindcraft/self_prompter.stub.js).
    "!setMode", "!newAction", "!goal", "!endGoal",
}

_CMD_RE = re.compile(r"!\w+(?:\([^)]*\))?", re.UNICODE)
_TAIL_NOISE_RE = re.compile(r"[\*\$#]{2,}")
_WS_RE = re.compile(r"\s{2,}")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)

# Andy-4 — это Llama-8B-R1 fine-tune, льёт reasoning в открытый текст.
# Закрытые пары вырезаем целиком; "висячий" <think> без закрытия (max_tokens
# обрезал хвост) — режем всё от тега до конца.
_THINK_PAIR_RE = re.compile(
    r"<think(?:ing)?>.*?</think(?:ing)?>",
    re.DOTALL | re.IGNORECASE,
)
_THINK_OPEN_DANGLING_RE = re.compile(
    r"<think(?:ing)?>.*\Z",
    re.DOTALL | re.IGNORECASE,
)
# Иногда модель забывает открывающий тег и сразу пишет "</think>...".
_THINK_CLOSE_LEADING_RE = re.compile(
    r"\A.*?</think(?:ing)?>",
    re.DOTALL | re.IGNORECASE,
)


def strip_reasoning(text: str) -> str:
    """Убирает <think>...</think> и его варианты у R1-моделей."""
    text = _THINK_PAIR_RE.sub("", text)
    text = _THINK_CLOSE_LEADING_RE.sub("", text)
    text = _THINK_OPEN_DANGLING_RE.sub("", text)
    return text.strip()


def strip_info_commands(text: str) -> str:
    """Удаляет info-команды Mindcraft и хвостовой мусор вида '***' / '$$$'."""
    def _drop(m: "re.Match[str]") -> str:
        cmd = m.group(0)
        name_match = re.match(r"!\w+", cmd)
        if name_match and name_match.group(0) in INFO_COMMANDS:
            return ""
        return cmd

    cleaned = _CMD_RE.sub(_drop, text)
    cleaned = _TAIL_NOISE_RE.sub("", cleaned)
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned


def _word_set(text: str, min_len: int = 3) -> set:
    text = _PUNCT_RE.sub(" ", text.lower())
    return {w for w in text.split() if len(w) >= min_len}


def jaccard(a: str, b: str) -> float:
    sa, sb = _word_set(a), _word_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


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
        model_name: str = "t-tech/T-lite-it-2.1:Q4_K_M",
        stm_capacity: int = 50,
        ltm_max_size: int = 1000,
        similarity_threshold: float = 0.8,
        similarity_min_words: int = 5,
        temperature_override: Optional[float] = None,
    ):
        self.name = name
        self.character = character
        self.llm = llm
        self.model_name = model_name
        self.stm = STM(capacity=stm_capacity)
        self.ltm = LTM(max_size=ltm_max_size)
        self.last_perception: str = "(пока не понятно где ты)"
        self.similarity_threshold = similarity_threshold
        self.similarity_min_words = similarity_min_words
        self.temperature_override = temperature_override
        # Имя последнего реального игрока, говорившего со Странником.
        # Нужно для action_grounder — чтобы в !followPlayer знать кому следовать.
        self.last_speaker: Optional[str] = None

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
        # Парсим Mindcraft user-message в типизированный вид:
        # speaker / реплика / системные события.
        parsed = parse_user_message(user_message)
        if parsed.speaker:
            self.last_speaker = parsed.speaker
        # Системные события (Recent behaviors log, drowning, ...) кладём в STM
        # как perceptions. Это первый шаг к настоящему восприятию мира.
        for evt in parsed.system_events:
            self.observe(evt, perception_type="felt")
        # Реплика игрока — отдельным событием. Если speaker неизвестен и
        # реплики нет (пустой SYSTEM-тик) — ничего не пишем.
        if parsed.text:
            who = parsed.speaker or "(?)"
            self.observe(f"{who}: {parsed.text}", perception_type="heard")

        # Собираем наш system prompt — характер + STM + LTM.
        # perception_summary даём не сырой dump от Mindcraft, а реплику игрока.
        # State мира пока пустой — это задача B2 (perception narrator).
        perception = parsed.text or (parsed.system_events[0] if parsed.system_events else "")
        system_prompt = build_system_prompt(
            self.character,
            self.stm,
            self.ltm,
            perception_summary=perception[:500] or "(тихо)",
        )

        # Реконструируем messages: наш system + diaлоговая история без system.
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if history:
            for m in history:
                if m.get("role") in ("user", "assistant"):
                    messages.append(m)
        # В user-роль кладём очищенный текст (без "***" и SYSTEM-префиксов),
        # чтобы LLM не отвлекался на Mindcraft-артефакты.
        clean_user = parsed.text or " ".join(parsed.system_events) or user_message
        messages.append({"role": "user", "content": clean_user})

        effective_temp = (
            self.temperature_override
            if self.temperature_override is not None
            else temperature
        )
        result = await self.llm.chat_completion(
            messages=messages,
            model=self.model_name,
            max_tokens=max_tokens,
            temperature=effective_temp,
            # slot_id и cache_prompt — только для llama.cpp; Ollama их игнорирует
        )

        # OpenAI-формат: choices[0].message.content
        choices = result.get("choices", [])
        if not choices:
            return "…"
        raw = choices[0].get("message", {}).get("content", "").strip()

        # 1a) Режем reasoning-теги (Andy-4 = Llama-R1 льёт <think> в открытый текст,
        # внутри теряет identity и галлюцинирует имя другого бота).
        cleaned = strip_reasoning(raw)
        # 1b) Стрипим Mindcraft info-команды (главный источник self-loop).
        cleaned = strip_info_commands(cleaned)

        # 2) Similarity drop ≥0.8 к последней содержательной реплике (П4 редуц.).
        # Пропускаем "…" — иначе спам, разбавленный молчанием, проходит фильтр.
        last_said = next(
            (
                e for e in reversed(self.stm.events)
                if e.perception_type == "said"
                and len(_word_set(e.content)) >= self.similarity_min_words
            ),
            None,
        )
        if (
            cleaned
            and last_said is not None
            and len(_word_set(cleaned)) >= self.similarity_min_words
            and jaccard(cleaned, last_said.content) >= self.similarity_threshold
        ):
            cleaned = "…"

        # 3) Если после стрипа пусто — тоже молчим.
        if not cleaned:
            cleaned = "…"

        # 4) Action grounding: если в narrative-ответе есть намерение движения
        # ("иду", "стою", "отойду") — дописываем одну Mindcraft-команду.
        # Это мост между "живой речью" и mineflayer-skill вызовом.
        # Модель сама команд не пишет (в prompt разрешено говорить о намерении
        # своими словами), middleware "читает между строк".
        action = ground_action(cleaned, self.last_speaker)
        final = f"{cleaned} {action}" if action else cleaned

        # Записываем собственный ответ в STM как "сказал/сделал".
        # В STM кладём именно cleaned (без !command) — для similarity-фильтра
        # и для будущего нарратива "что я сказал".
        self.stm.add(Event(
            timestamp=time.time(),
            perception_type="said",
            content=cleaned[:300],
        ))
        if action:
            self.stm.add(Event(
                timestamp=time.time(),
                perception_type="did",
                content=action,
            ))

        return final
