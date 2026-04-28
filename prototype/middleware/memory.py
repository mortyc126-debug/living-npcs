"""Memory layer — STM (события дня) + LTM (provenance-tagged beliefs).

Реализация Принципа 1 + retraction-механизма из ADR-004.
Шаг 1: упрощённо, без consolidation. Sleep + retraction — Шаги 4-5.
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Source(str, Enum):
    """Иерархия источников из ADR-004: direct > inferred > heard > dreamed."""

    DIRECT = "direct_perception"
    INFERRED = "inferred"
    HEARD = "heard"
    DREAMED = "dreamed"

    @property
    def priority(self) -> int:
        return {"direct_perception": 4, "inferred": 3, "heard": 2, "dreamed": 1}[self.value]


@dataclass
class Event:
    """Запись в STM — событие текущего дня."""

    timestamp: float
    perception_type: str           # "saw", "heard", "felt", "did", "said"
    content: str                   # человекочитаемое описание
    affect_signature: tuple = (0.0, 0.0, 0.0)  # (v, a, d) — воздействие на VAD


@dataclass
class Belief:
    """Запись в LTM — provenance-tagged убеждение.

    Шаг 1: confidence остаётся статичной.
    Шаги 4-5: добавляется decay и contradiction handling.
    """

    id: str
    content: str
    source: Source
    confidence: float              # [0.0, 1.0]
    last_touched: float            # timestamp последнего подтверждения
    witnessed_at: float            # когда впервые
    affect_signature: tuple = (0.0, 0.0, 0.0)
    source_detail: Optional[str] = None  # например, "heard:NPC_X"

    def decay(self, now: float, rate: float) -> None:
        """Weibull-like decay — Шаг 5. Здесь — заглушка."""
        elapsed_days = max(0.0, (now - self.last_touched) / 86400.0)
        # экспоненциальный спад на старте; полноценный Weibull позже
        self.confidence *= math.exp(-rate * elapsed_days)
        self.confidence = max(0.0, self.confidence)


class STM:
    """Short-Term Memory — буфер событий текущего дня."""

    def __init__(self, capacity: int = 50):
        self.capacity = capacity
        self.events: List[Event] = []

    def add(self, event: Event) -> None:
        self.events.append(event)
        if len(self.events) > self.capacity:
            self.events.pop(0)

    def recent(self, n: int = 10) -> List[Event]:
        return self.events[-n:]

    def clear(self) -> None:
        """Вызывается во сне после consolidation."""
        self.events.clear()

    def to_prompt_lines(self, n: int = 10) -> str:
        if not self.events:
            return "(ничего недавно не происходило)"
        lines = []
        for e in self.recent(n):
            lines.append(f"- [{e.perception_type}] {e.content}")
        return "\n".join(lines)


class LTM:
    """Long-Term Memory — provenance-tagged beliefs.

    Шаг 1: in-memory, без сна, без decay.
    Шаги 4-5: persistence + Weibull decay + contradiction detection.
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.beliefs: List[Belief] = []
        self._next_id = 0

    def add(self, content: str, source: Source, confidence: float = 0.7,
            affect: tuple = (0.0, 0.0, 0.0), source_detail: Optional[str] = None) -> Belief:
        now = time.time()
        b = Belief(
            id=f"belief_{self._next_id}",
            content=content,
            source=source,
            confidence=confidence,
            last_touched=now,
            witnessed_at=now,
            affect_signature=affect,
            source_detail=source_detail,
        )
        self._next_id += 1
        self.beliefs.append(b)
        return b

    def to_prompt_lines(self, top_n: int = 10) -> str:
        """Top-N по confidence — для system prompt."""
        if not self.beliefs:
            return "(ничего не помнишь о своём прошлом)"
        sorted_b = sorted(self.beliefs, key=lambda b: b.confidence, reverse=True)
        lines = [f"- {b.content} ({b.source.value}, ~{int(b.confidence*100)}%)"
                 for b in sorted_b[:top_n]]
        return "\n".join(lines)
