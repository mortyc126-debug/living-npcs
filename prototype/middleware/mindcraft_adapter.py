"""Mindcraft transport adapter.

Изолирует middleware от формата сообщений Mindcraft. Если завтра уйдём
с Mindcraft на airi или свой mineflayer-клиент — заменим этот модуль,
ядро (cognitive_loop) не тронем.

Сейчас закрывает две задачи:
  1. parse_user_message — разбор того, что Mindcraft кладёт в user-роль.
     Формат:  "<player>: <text>***"  или  "SYSTEM: <event>".
  2. ground_action — мост narrative-ответа модели → Mindcraft-skill вызов.
     Берёт намерение из русского текста ("иду", "стою", "отойду") и
     возвращает одну команду вида !followPlayer("...", 3), которую
     Mindcraft парсит и исполняет.

Полноценный perception narrator (state → "ты стоишь у акации, рядом
игрок") — задача B2 (см. ADR в комментариях коммита).
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


# --- 1. Parser -----------------------------------------------------------

# Mindcraft в конце реплики добавляет "***" (или "**", "*") как маркер.
_TAIL_MARKER_RE = re.compile(r"\s*\*+\s*$")

# "Morty_C126: Follow me", "Player_2: text"
# Имя — латиница + цифры + _, начинается с буквы или _.
_SPEAKER_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", re.DOTALL)


@dataclass
class MindcraftMessage:
    """Разобранное user-сообщение от Mindcraft."""

    speaker: Optional[str] = None        # имя игрока, если реплика от него
    text: str = ""                       # сама реплика (без префикса/маркера)
    system_events: List[str] = field(default_factory=list)
    raw: str = ""                        # оригинал — для логов и отладки

    @property
    def is_system_only(self) -> bool:
        return self.speaker is None and not self.text and bool(self.system_events)

    @property
    def is_empty(self) -> bool:
        return not self.text and not self.system_events


def parse_user_message(raw: str) -> MindcraftMessage:
    """Разбирает то, что Mindcraft кладёт в user.content.

    Возможные формы:
      "Morty_C126: Follow me***"
      "SYSTEM: Recent behaviors log:\\nFighting phantom!\\nMorty_C126: Jump up***"
      "SYSTEM:" (пустой idle-тик)
      "Привет" (редко — без префикса)
    """
    msg = MindcraftMessage(raw=raw)
    if not raw:
        return msg

    # Сначала вытащим SYSTEM-блоки. Они могут быть склеены с репликой игрока
    # через переносы строк ("SYSTEM: ...\nMorty_C126: Jump up").
    text = raw
    system_events: List[str] = []

    # Разбираем построчно — каждый префикс начинает свой блок.
    lines = text.split("\n")
    current_role: Optional[str] = None
    current_buf: List[str] = []
    blocks: List[tuple] = []  # (role, content)

    def flush() -> None:
        if current_role is not None and current_buf:
            blocks.append((current_role, "\n".join(current_buf).strip()))

    for line in lines:
        if line.startswith("SYSTEM:"):
            flush()
            current_role = "SYSTEM"
            current_buf = [line[len("SYSTEM:"):].strip()]
            continue
        m = _SPEAKER_RE.match(line)
        if m:
            flush()
            current_role = m.group(1)
            current_buf = [m.group(2)]
            continue
        # продолжение текущего блока
        if current_role is not None:
            current_buf.append(line)
        else:
            # без префикса вообще — копим как fallback-text
            current_buf.append(line)
            current_role = current_role or "_PLAIN"
    flush()

    # Если префикс не появился — считаем всё это plain text от неизвестного.
    if not blocks:
        cleaned = _TAIL_MARKER_RE.sub("", raw).strip()
        msg.text = cleaned
        return msg

    # Последний player-блок — реальная реплика, остальное — SYSTEM/контекст.
    for role, content in blocks:
        cleaned = _TAIL_MARKER_RE.sub("", content).strip()
        if not cleaned:
            continue
        if role == "SYSTEM":
            system_events.append(cleaned)
        elif role == "_PLAIN":
            # plain text без префикса — кладём в text как реплику без автора
            msg.text = cleaned
        else:
            # это игрок — последний выигрывает
            msg.speaker = role
            msg.text = cleaned

    msg.system_events = system_events
    return msg


# --- 2. Action grounder --------------------------------------------------

# Намерения. Простые word-boundary паттерны на русском (T-lite пишет на нём).
# Если придёт английский — ничего страшного, просто не сматчим.
# Отрицания обрабатываем грубо: проверяем "не " перед глаголом в окне 8 chars.
_INTENT_FOLLOW = re.compile(
    r"\b(иду|следую|пойд[уе]м?|пошёл за|пошла за|иду за|иду к тебе|следом|за тобой)\b",
    re.IGNORECASE,
)
_INTENT_STOP = re.compile(
    r"\b(сто[юя]|стану|остановлюсь|остановилс|стой|погоди|жду|подожду|останусь)\b",
    re.IGNORECASE,
)
_INTENT_AWAY = re.compile(
    r"\b(отойду|отступлю|уйду|отбегу|подальше)\b",
    re.IGNORECASE,
)
_INTENT_NEAR = re.compile(
    r"\b(подойду|приду|приближусь|подбегу)\b",
    re.IGNORECASE,
)
_INTENT_ATTACK = re.compile(
    r"\b(нападаю|атакую|бью|ударю|защищаюсь|убью)\b",
    re.IGNORECASE,
)

# Отрицания, ищем в пределах одной фразы перед глаголом.
_NEGATION_RE = re.compile(
    r"\b(не|нет|никуда|никогда|ни\s*шагу)\b",
    re.IGNORECASE,
)
_CLAUSE_SEPS = ".,;!?\n"


def _clause_before(text: str, end: int) -> str:
    """Возвращает текст текущей фразы — от последнего знака препинания до end."""
    start = 0
    for sep in _CLAUSE_SEPS:
        i = text.rfind(sep, 0, end)
        if i + 1 > start:
            start = i + 1
    return text[start:end]


def _has_intent(text: str, pattern: re.Pattern) -> bool:
    """Совпадение намерения, не закрытое отрицанием в той же фразе."""
    for m in pattern.finditer(text):
        clause_left = _clause_before(text, m.start())
        if _NEGATION_RE.search(clause_left):
            continue
        return True
    return False


def ground_action(narrative: str, last_speaker: Optional[str]) -> Optional[str]:
    """Из свободного текста модели → одна Mindcraft-команда (или None).

    Возвращаем None если намерение не распознано — модель просто говорит,
    Mindcraft не делает физического действия. Это ОК для амнезика.
    """
    if not narrative or narrative.strip() == "…":
        return None

    # Порядок важен: stop сильнее follow, attack сильнее всего.
    if _has_intent(narrative, _INTENT_ATTACK):
        # цель атаки определить трудно — оставляем без аргумента,
        # Mindcraft возьмёт ближайшую враждебную сущность через mode.
        # Если нет — !attack без args даст ошибку, но и это редкий путь.
        return None  # не грундим — слишком хрупко на Шаге 1
    if _has_intent(narrative, _INTENT_STOP):
        return "!stay(5)"  # стоит 5 минут или до новой команды
    if _has_intent(narrative, _INTENT_AWAY):
        return "!moveAway(5)"
    if _has_intent(narrative, _INTENT_NEAR) and last_speaker:
        return f'!goToPlayer("{last_speaker}", 3)'
    if _has_intent(narrative, _INTENT_FOLLOW) and last_speaker:
        return f'!followPlayer("{last_speaker}", 3)'
    return None
