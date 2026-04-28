"""Character state — HEXACO ядро + VAD состояние.

Реализация Принципа 2 (характер как паттерн параметров) для Шага 1.
На Шаге 1 параметры идут в промпт; на Шаге 3 переходят в control vectors.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict


@dataclass
class HEXACO:
    """Шесть осей характера. Стабильное ядро, дрейфует только во сне."""

    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5
    honesty_humility: float = 0.5

    def clamp(self) -> None:
        for k, v in asdict(self).items():
            setattr(self, k, max(0.0, min(1.0, v)))

    def to_prompt_lines(self) -> str:
        """Возвращает короткое описание характера для system prompt."""
        return (
            f"- Любопытство: {self.openness:.2f}\n"
            f"- Осторожность/организованность: {self.conscientiousness:.2f}\n"
            f"- Открытость к людям: {self.extraversion:.2f}\n"
            f"- Доброжелательность: {self.agreeableness:.2f}\n"
            f"- Тревожность: {self.neuroticism:.2f}\n"
            f"- Честность: {self.honesty_humility:.2f}"
        )


@dataclass
class VAD:
    """Эмоциональное состояние: Valence-Arousal-Dominance.
    Меняется в реальном времени от событий, плавно затухает к baseline во сне.
    """

    valence: float = 0.0      # хорошо/плохо
    arousal: float = 0.0      # спокойно/возбуждено
    dominance: float = 0.0    # бессилен/в контроле

    def clamp(self) -> None:
        for k, v in asdict(self).items():
            setattr(self, k, max(-1.0, min(1.0, v)))

    def apply_delta(self, dv: float = 0.0, da: float = 0.0, dd: float = 0.0) -> None:
        self.valence += dv
        self.arousal += da
        self.dominance += dd
        self.clamp()

    def decay_to_baseline(self, baseline: "VAD", rate: float = 0.1) -> None:
        """Постепенный возврат к baseline (вызывается каждый тик / во сне)."""
        self.valence += (baseline.valence - self.valence) * rate
        self.arousal += (baseline.arousal - self.arousal) * rate
        self.dominance += (baseline.dominance - self.dominance) * rate

    def to_prompt_lines(self) -> str:
        """Описание текущего состояния словами, не числами — для LLM."""

        def label(v: float, neg: str, pos: str, neutral: str) -> str:
            if v < -0.4:
                return neg
            if v > 0.4:
                return pos
            return neutral

        v = label(self.valence, "плохо себя чувствует", "в хорошем настроении", "ровное состояние")
        a = label(self.arousal, "расслаблен", "напряжён", "спокойно сосредоточен")
        d = label(self.dominance, "потерян, не у дел", "уверен в себе", "просто наблюдает")
        return f"- Самочувствие: {v}\n- Внутреннее напряжение: {a}\n- Чувство контроля: {d}"


@dataclass
class CharacterState:
    """Полное состояние характера одного NPC."""

    hexaco: HEXACO = field(default_factory=HEXACO)
    vad: VAD = field(default_factory=VAD)
    vad_baseline: VAD = field(default_factory=VAD)
    # Лоскутные параметры на привязанности появятся когда возникнут связи.
    # На Шаге 1 — пусто.
    attachments: Dict[str, Dict[str, float]] = field(default_factory=dict)

    @classmethod
    def from_config(cls, cfg: dict) -> "CharacterState":
        h = HEXACO(**cfg.get("hexaco", {}))
        v = VAD(**cfg.get("vad", {}))
        baseline = VAD(**cfg.get("vad", {}))  # baseline = стартовое VAD
        return cls(hexaco=h, vad=v, vad_baseline=baseline)
