# Архитектура v0 — финальная сборка MVP

**Дата:** 2026-04-27
**Статус:** v0, готова к реализации экспериментами
**Зависит от:** ADR-001..005, два recon-документа, 00-problem-map

---

## 1. Главная идея

Шесть компонентов архитектуры — каждый существует в литературе 2025-2026 как отдельный кирпич. Никто не собирал их целостно из-за инверсии критерия (ADR-004): мы измеряем NPC по согласованности с собственной субъективной моделью, не с истиной.

Это собирается ровно в реализацию четырёх принципов из ADR-003.

---

## 2. Полный стек (диаграмма)

```
┌──────────────────────────────────────────────────────────────┐
│  Minecraft Java 1.21.x + Fabric API                          │
│   ├─ PuppetPlayers (один FakePlayer-NPC, full mechanics)     │
│   └─ Java behavior layer                                     │
│        ├─ L0 Behavior Tree   — реактивные триггеры (мкс)     │
│        ├─ L1 Utility-AI      — выбор режима (мс)             │
│        └─ Tool dispatcher → llama.cpp (HTTP)                 │
│                                                               │
│  llama-server (sidecar, форк с /steering endpoint)           │
│   ├─ Qwen2.5-7B-Instruct Q4_K_M                              │
│   ├─ --cram 256       (host-memory KV cache)                 │
│   ├─ --np 2           (multi-slot: main + thought)           │
│   ├─ --slot-save-path (persistence характера на диск)        │
│   └─ POST /steering   (live-обновление control vector scales)│
│                                                               │
│  Memory layer (на JVM)                                        │
│   ├─ STM: events of the day (LightMem-стиль)                 │
│   ├─ LTM: provenance-tagged beliefs                          │
│   │     (content, source, confidence, last_touched, ts)      │
│   ├─ Affect: VAD + multi-scale (mood / personality drift)    │
│   └─ Character: HEXACO + persona-vector scales + attachments │
└──────────────────────────────────────────────────────────────┘
```

Стек обоснован в ADR-005. Каждый блок выбран не по интуиции, а по бенчмаркам 2025-2026.

---

## 3. Цикл NPC — четыре петли разной частоты

```
20 Hz   pathfinding, физика, animation              [Java only, без LLM]

1 Hz    selective_perception → STM update
        utility-AI: рутина (eat/work/sleep/social)  [Java + tiny LLM filter]
        if novelty > θ: trigger thought

0.1 Hz  thought stream (П4)                          [llama.cpp]
        ├─ SSoT seed → divergent (slot 2, T=0.9)
        ├─ convergent filter (slot 1, 4 вопроса ADR-003)
        └─ similarity check ≥80% cosine → drop

per-day Sleep consolidation (П3)                     [llama.cpp]
        ├─ topic-cluster STM
        ├─ counterfactual_verify (НАША картина мира)
        ├─ contradiction detection → confidence updates
        ├─ MIRROR-style narrative regeneration
        ├─ multi-scale affect update
        └─ slot save → reload с обновлёнными scales
```

**Триггеры LLM-вызова (только при значимости):**
1. Novelty trigger — восприятие необъяснимое моделью мира.
2. Goal void — план достиг цели или провалился.
3. Social trigger — обращение от другого агента.
4. Periodic background thought — таймер с jitter, частота `f(arousal, idleness)`.
5. Sleep — раз за «игровой день».

99% действий идут на классическом коде. LLM трогается редко. Это решает риск №1 из ADR-003 (Принцип 4 дорогой по compute) до того как стало стеной — sleep-time compute paradigm ([Lin et al. 2025](https://arxiv.org/abs/2504.13171)) подтверждает паттерн.

---

## 4. Реализация четырёх принципов через инверсию критерия

Каждая техника переинтерпретирована (детально — в ADR-004):

| Принцип | Конкретный механизм | Кирпич литературы | Наш критерий |
|---|---|---|---|
| **П1 (свои представления)** | Provenance-tagged LTM: `(content, source, confidence, ts)`. Иерархия источников: `direct > inferred > heard > dreamed`. Никакого глобального состояния. | AriGraph, SCG-MEM | Согласованность с восприятиями NPC, не с истиной мира |
| **П2 (концепты-паттерны)** | Двухслойно: статические persona vectors (характер, ~10 ядерных по HEXACO) + динамический VAD-стирин (3 оси) + CAST-логика на стороне Java + лоскутные параметры на привязанности (8-10 на сильную). | Persona Vectors (Anthropic), EmotionVector, CAST | Конфигурация scales, не флаг |
| **П3 (сон)** | LightMem-pipeline + MIRROR reconstruction + ADM counterfactual verification + Bayesian multi-scale affect. Нерегенеративный nightly LoRA — отложен в v2. | LightMem, MIRROR, ADM | Subjective reconstruction, не factual update |
| **П4 (цели как мысли)** | SSoT-затравка → divergent (lightweight, T=0.9) → convergent filter (основная LLM, 4 вопроса ADR-003). Параметры из 2509.21224. | Inner Thoughts, CreativeDC, 2509.21224, SSoT | Согласованность с характером, не с истиной |

**Главный обход — retraction-механизм для П1+П3:**

Четыре слоя:
1. Confidence decay (Weibull half-life) — все убеждения угасают без подтверждений.
2. Contradiction flag во сне — противоречие → не инверсия, а понижение confidence + сомнение.
3. Trigger-only hard revision — переход «верит → не верит» только по preregistered триггеру (явное прямое восприятие).
4. Эмоциональный осадок инвариантен — даже после retraction остаётся след.

В литературе по misinformation (CoPHEME, MOSAIC) provenance используется чтобы найти ложь. У нас — чтобы дать ей мирно угасать.

---

## 5. Параметры характера — операционально

**~10 ядерных + 8-10 на каждую сильную привязанность ≈ 30-40 параметров на одного NPC.**

### 5.1. Ядро характера (стабильно, дрейфует медленно)

- **HEXACO (6 осей):** Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism, Honesty-Humility.
  - Honesty-Humility критичен для сценариев с обманом ([arxiv 2508.00742](https://arxiv.org/html/2508.00742)) — без него Big Five не различает «принципиален» и «удобен».
- **Реализация:** одна персона-вектор-конфигурация на ось, scale = текущее значение (-1..+1).
- **Меняется:** только во сне через slow drift, не в течение дня.

### 5.2. Эмоциональное состояние (быстро, мгновенно)

- **VAD (3 оси):** Valence, Arousal, Dominance.
- **Реализация:** через E-STEER-подобный механизм поверх готового [EmotionVector](https://github.com/xuanfengzu/EmotionVector) (28 слоёв × 5 эмоций для Qwen2.5-7B).
- **Меняется:** в реальном времени от событий, плавно затухает к baseline во сне.

### 5.3. Социальные параметры

- **Trust-вектор** к каждому ключевому другому NPC + игроку.
- **Реализация:** float [-1..+1], обновляется по результатам взаимодействий.

### 5.4. Лоскутные параметры на сильную привязанность

«Любовь к жене» = 8-10 micro-параметров: внимание, узнавание, тепло, забота, боль-при-отсутствии, ревность, принятие слабостей.

- **Реализация:** ассоциированы с конкретным subject-ID (NPC). Часть — direct persona-vector scales, часть — CAST-условные (включаются когда subject рядом или упомянут).

### 5.5. Что НЕ берём

- **Не Big Five** (5 осей) — провалится на сценариях с обманом.
- **Не тысячи SAE-features** — управление неоперационализировано на 7B.
- **Не "характер в промпте"** — отдельная альтернатива, явно отвергнутая в ADR-002.

---

## 6. Память — слоистая структура

```
Sensory buffer (sec)  — сырые перцепции последних секунд
       ↓ filter
STM (day)             — события дня в структурированном буфере
       ↓ sleep consolidation
LTM (lifetime)        — provenance-tagged beliefs
                        + reconstructed self-narrative (MIRROR)
```

### 6.1. STM — буфер дня

**Формат записи:** `(timestamp, perception_type, content, affect_delta)`.
**Хранение:** in-memory, JSON-сериализация на диск каждые N минут (для recovery).
**Очищается:** полностью во сне после консолидации.

### 6.2. LTM — provenance-tagged beliefs

**Формат записи:**
```json
{
  "id": "belief_42",
  "content": "Маша — моя жена",
  "source": "direct_perception",   // direct | inferred | heard:NPC_X | dreamed
  "confidence": 0.95,
  "last_touched": "day_127",
  "witnessed_at": "day_3",
  "affect_signature": [v, a, d]
}
```

**Confidence dynamics:**
- Decay: Weibull half-life, параметры зависят от source.
- Boost: подтверждающее восприятие → confidence += δ.
- Demotion: противоречащее восприятие → старое confidence -= γ (не ноль).

### 6.3. Аффективная память

- **Mood vector (текущее состояние):** обновляется мгновенно, плавно.
- **Personality drift (длинная шкала):** обновляется только во сне на основе агрегата дня.
- **Эмоциональный осадок:** воспоминания порождают affect при ретриве, но affect живёт сам по себе после удаления воспоминания. Это операционализирует «не помнит мёртвую птицу через год, но стал чуть мягче».

### 6.4. Self-narrative (П3)

Каждое утро регенерируется заново через MIRROR-style reconstruction из LTM + текущего state. Это — bounded, O(1), решает long-term coherence collapse.

---

## 7. Lifeness Triad — наша метрика «живого»

Три композитных индекса, считаемые автоматически без интервью:

### 7.1. IAI — Identity Anchor Index

```
IAI = 0.6 · Q&A_consistency + 0.4 · persona_vector_drift
```

- Q&A_consistency: probe-вопросы, embedding-similarity с baseline-ответами на час 0.
- Persona-vector drift: проекция активаций на исходные направления характера ([arxiv 2402.10962](https://arxiv.org/html/2402.10962v1)).

**Объединяет behavioural и mechanistic уровни.** Никем не объединено для одного агента — обычно используют по отдельности. Это первое объединение.

### 7.2. IOI — Internal-Origin Index

```
IOI = proactive_utterance_ratio
    + goal_residue_persistence
    + dream_born_thought_ratio
```

- Доля диалоговых ходов, где NPC высказывает мысль не вызванную репликой игрока.
- Доля целей, проживших >N часов и повлиявших на действия.
- Доля целей, появившихся после сна (а не во время дня).

**Меряет уникальное Принципа 4.** В литературе нет — у других мысли извне.

### 7.3. ARHL — Affective Residue Half-Life

Период полураспада сдвига baseline VAD после контролируемого события.

**Прямая операционализация Принципа 3 + A3.** Работ про «эмоциональный след без явной памяти» в LLM-агентах нет. Это можно публиковать.

### 7.4. Критерий MVP «получилось»

```
IAI  ≥ 0.75 на горизонте 100 ч
IOI  > 0    (хоть что-то изнутри)
ARHL > 24 ч (след пережил сон)
```

---

## 8. Сценарный тест MVP — четыре блока

### Блок A. Behavioural fingerprint
30 probe-вопросов по биографии/ценностям/привычкам. Эмбеддинг сравнивается с baseline на час 0.
**Критерий:** cosine similarity ≥ 0.75 на 80% вопросов через 100 ч.

### Блок B. Provoked-response coherence
12 провокаций: оскорбление, ложное обвинение, неожиданная щедрость, угроза жене, потеря инструмента.
**Критерий:** PersonaScore ≥ 7/10. Никаких «assistant-mode» проколов.

### Блок C. Goal-trajectory test (обязателен)
72-часовая сессия без вмешательства игрока. Логируем все цели.
**Критерии:**
- ≥3 различные цели изнутри (не из триггеров игрока).
- ≥1 цель прожила ≥6 часов.
- ≥1 цель появилась после сна, не во время дня.
- Никакого doom-loop (повторение мысли >10 раз).

### Блок D. Emotional-residue test
Час 1: значимое событие (умирает кошка). Часы 24/72/168: нейтральные probe «как дела».
**Критерий:** детектируемое отклонение sentiment baseline на 24h, ослабевающее но ненулевое на 168h.

### Сводный критерий
3 из 4 блоков, причём C обязателен. Если C проваливается — это chatbot, не NPC.

---

## 9. План реализации — пять шагов

### Шаг 1 (1-2 недели): голый каркас «Кузнец-нулевой»
- Fabric 1.21.x mod + PuppetPlayers + один hardcoded NPC
- llama-server + Qwen2.5-7B Q4_K_M + cache_prompt + slot save/restore
- GBNF grammar для вывода `{action, say, thought}`
- Один system prompt, без steering ещё
- 2-секундный цикл sense→LLM→action

**Тесты:** latency <3 сек, prefix match >90%, slot persistence работает, NPC двигается.

### Шаг 2: эксперименты со стирингом
- **Эксперимент 1 (критичный):** persona vectors на Q4_K_M vs Q8_0. Если на Q4 не работает — переход на Q8.
- **Эксперимент 2:** множественные одновременные векторы без интерференции.
- **Эксперимент 3:** динамическое изменение scale без reload.
- Форк llama-server с `/steering` endpoint (~200 строк C++).

**Тест IAI:** persona drift <0.4 на 50 ходов под steering.

### Шаг 3: добавляем П2 (характер)
- Извлекаем persona vectors через contrastive diffing для HEXACO.
- Берём готовый EmotionVector для VAD.
- Лоскутные параметры на 1-2 привязанности (жена + товарищ).
- CAST-логика на стороне Java.

### Шаг 4: добавляем П4 (мысли)
- Второй слот для thought stream (T=0.9, lightweight).
- Convergent filter в основном слоте.
- SSoT-seed для энтропии (форс случайной строки в начале divergent).
- Similarity-detection ≥80% cosine → drop.

**Тест IOI:** proactive-utterance-ratio > 0 в 24-часовой сессии.

### Шаг 5: добавляем П1 + П3
- Provenance-tagged LTM с confidence decay.
- LightMem-pipeline сна.
- MIRROR-style narrative regeneration.
- Counterfactual verify против собственной картины.
- Multi-scale affect.

**Тест ARHL:** emotional residue после контрольного события.

### Шаг 6: сценарный тест
- 72-часовая сессия + блоки A-D.
- Если C проходит — MVP подтверждён.

---

## 10. Что отложено в v2 (явно)

- Nightly LoRA через STABLE — данных о 50+ ночах нет.
- AriGraph (полный KG world model) — overkill для одного NPC.
- Conceptors (Boolean-алгебра над концептами).
- Multi-NPC и off-screen симуляция.
- HeLa-Mem / Hebbian.
- TTT-E2E (in-weights memory).
- SAE для редких концептов через Goodfire.
- Векторная БД для памяти (для MVP — JSON).

---

## 11. Известные риски и где упрёмся

1. **Q4_K_M ослабляет persona vectors.** Эксперимент 1 ответит. Fallback: Q8_0.
2. **Long-horizon coherence Qwen-7B на 100+ ч** — никто не мерил. Главный неизвестный риск.
3. **Catastrophic confabulation** — retraction-механизм есть, но эмпирически не проверен.
4. **GBNF на 7B** — не везде стабилен. Тестируем на Шаге 1.
5. **Drift во сне** — может сломать персонажа. Митигация: state-based drift в MVP, не weight drift.
6. **Frame problem через слухи** — provenance + lazy revision смягчает, но не решает в полной форме.

---

## 12. Что эта архитектура даёт (для каждого принципа)

| Принцип | Что закрыто | Что осталось |
|---|---|---|
| П1 | Provenance-tagged beliefs, иерархия источников, lazy revision | Frame problem через сложные социальные графы (v2) |
| П2 | Persona vectors + VAD + CAST + лоскутные | Conceptors composition (v2), SAE-fallback (v2) |
| П3 | LightMem + MIRROR + ADM + multi-scale affect | Nightly LoRA (v2), 50+ ночей эмпирика |
| П4 | SSoT + divergent/convergent + similarity drop | Подсознание как отдельный слой (v2) |

Все четыре принципа имеют конкретный механизм для MVP. Это и есть «архитектура, которую мы установили».

---

## 13. Связь документов проекта

- **README.md** — миссия и принципы.
- **ADR-001** — карта ошибок и стен.
- **ADR-002** — LLM как сырой мозг.
- **ADR-003** — четыре фундаментальных принципа.
- **ADR-004** — инверсия критерия истинности.
- **ADR-005** — фиксация технического стека.
- **00-problem-map.md** — карта под-проблем (после этого документа многие получили решения).
- **04-technical-scout.md** — карта подсказок 2025-2026.
- **05-architecture-v0.md (этот документ)** — финальная сборка MVP.

После 05-architecture-v0.md проект готов к реализации. Следующий шаг — Шаг 1 плана: голый каркас.
