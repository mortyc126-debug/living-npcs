# ADR-005: Технический стек MVP

**Статус:** Принято
**Дата:** 2026-04-27
**Контекст сессии:** session 02, после двух волн разведки
**Зависит от:** ADR-001, ADR-002, ADR-003, ADR-004

---

## Решение

Для MVP («один NPC, в которого можно поверить») фиксируется конкретный технический стек. Каждый выбор обоснован эмпирическими данными из разведки 2025-2026, не интуицией.

---

## 1. Платформа модов: Fabric 1.21.x

**Выбрано:** Fabric API 1.21.x (последняя стабильная на момент решения).

**Альтернативы:** Forge (мёртв на 1.21+), NeoForge (стандарт для контентных модов, но избыточный для нашего случая).

**Обоснование:**
- Все актуальные LLM-NPC моды (sailex428/AI-NPC, SecondBrain, AI-Player) — Fabric. Готовые референсы.
- Быстрые обновления к новым версиям Minecraft.
- Лёгкое API, активная исследовательская экосистема.
- NeoForge даёт больше mixin-возможностей для глубоких изменений геймплея — но мы не делаем геймплей, мы делаем NPC.

**Риск:** если в будущем нужна интеграция с большими модпаками — может потребоваться переход на NeoForge. Это инженерный, не архитектурный риск.

---

## 2. Server-side NPC: PuppetPlayers

**Выбрано:** [PuppetPlayers](https://github.com/senseiwells/PuppetPlayers) — FakePlayer-обёртка для Fabric.

**Альтернативы рассмотрены:**
- **Citizens2** — Bukkit/Paper, не работает на Fabric напрямую.
- **Taterzens** — кастомная сущность; проблемы с инвентарями ([Issue #41](https://github.com/samolego/Taterzens/issues/41)), не сражается как игрок.
- **Carpet `/player`** — полные player-mechanics, но управление только через Scarpet/команды, нет Java API.
- **Mineflayer** — внешний JS-клиент; добавляет node-зависимость на каждого NPC.

**Обоснование:**
- Это `FakePlayer`, наследует от `ServerPlayerEntity`. **Все игровые механики работают как у настоящего игрока:** инвентарь, hunger, broken blocks правильно дропают, мобы реагируют как на игрока.
- **Спит в кровати** — критично для Принципа 3 (сон-консолидация).
- Активная поддержка 1.21.5-1.21.11.
- Программируемый API цепочек действий с задержками — ложится на L0/L1 двухскоростной архитектуры.

**Риск:** если PuppetPlayers перестанет поддерживаться — fallback на форк Carpet `/player` с Java-API (как делает AI-Player).

---

## 3. LLM рантайм: llama.cpp

**Выбрано:** llama.cpp в режиме `llama-server` с флагами `--cram 256 --np 2 --slot-save-path`.

**Альтернатива:** vLLM (с EasySteer для стиринга).

**Обоснование (бенчмарки 2025-2026):**
- [Red Hat сент 2025](https://developers.redhat.com/articles/2025/09/30/vllm-or-llamacpp-choosing-right-llm-inference-engine-your-use-case): «llama.cpp wins for single-user/low-concurrency, consumer hardware, fast startup».
- [BSWEN март 2026](https://docs.bswen.com/blog/2026-03-15-vllm-vs-llamacpp-speed/): «For single-user local inference, llama.cpp often matches or beats vLLM».
- vLLM выигрывает на батчах 16+ пользователей. У нас никогда не будет такого профиля для MVP.
- vLLM на 7B Q4 требует 12+ GB VRAM (issue [#27934](https://github.com/vllm-project/vllm/issues/27934) — V1 engine падает на RTX 3060 12GB). llama.cpp комфортен с 8 GB.

**Ключевые фичи llama.cpp, на которых стоит архитектура:**
- `--cram 256` — host-memory KV cache ([Discussion #20574](https://github.com/ggml-org/llama.cpp/discussions/20574)). Персональный prefix каждого NPC хранится в RAM, hot-swap в GPU за миллисекунды.
- `--np 2` — multi-slot. Параллельные слоты (main + thought stream) с независимыми KV-cache.
- `/slots/<id>/save` и `/slots/<id>/restore` ([Discussion #20572](https://github.com/ggml-org/llama.cpp/discussions/20572)) — **persistence характера на диск между сессиями игры**. Критично для П3.
- `--control-vector` ([PR #5970](https://github.com/ggml-org/llama.cpp/pull/5970), смержен с 2024) — встроенная поддержка activation steering.

**Риск:** нет тензорного параллелизма для multi-GPU. Не критично для одной 8-12GB карты.

---

## 4. Модель: Qwen2.5-7B-Instruct Q4_K_M

**Выбрано:** Qwen2.5-7B-Instruct в квантовании Q4_K_M (GGUF).

**Альтернативы рассмотрены:**
- **Mistral-Nemo-12B (RPMax)** — лучше «творческий голос», но больше VRAM. Кандидат для диалогового слоя в v2.
- **Llama-3.1-8B / Llama-3.3** — Llama-3.3 70B не для локального железа. 8B уступает Qwen2.5-7B на role-play и instruction following.
- **Gemma 3 / Phi-4** — Gemma имеет проблемы с cache reuse в llama.cpp ([Issue #21468](https://github.com/ggml-org/llama.cpp/issues/21468)), Phi-4 менее dialogue-friendly.
- **3B-модели** — плохо держат структурированный вывод даже с GBNF ([arxiv 2501.10868](https://arxiv.org/html/2501.10868v1)). Минимальная разумная для нас — 7B.

**Обоснование:**
- [Cognitive Agents in Urban Mobility (PMC sept 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12451180/): Qwen2.5-7B справился с симуляцией городской толпы 20 дней — прямой прецедент.
- [Qwen2.5 blog](https://qwenlm.github.io/blog/qwen2.5-llm/): «more resilient to the diversity of system prompts, enhancing role-play».
- Persona vectors Anthropic тестировались именно на Qwen2.5-7B ([arxiv 2507.21509](https://arxiv.org/abs/2507.21509)) — готовый плацдарм для П2.
- [EmotionVector](https://github.com/xuanfengzu/EmotionVector) уже имеет готовые векторы для Qwen2.5-7B на 5 эмоций × 28 слоёв.

**Производительность:**
- RTX 3060 12GB Q4_K_M: ~40-50 tok/s. Реплика NPC ~80-150 токенов = 2-3 сек.
- RTX 4070: ~50-70 tok/s.

**Риск:** Q4_K_M уменьшает точность активаций — может ослабить эффект persona vectors. Это **первый эксперимент проекта** (см. 04-technical-scout.md, эксперимент 1). Если на Q4 не работает — переход на Q8_0 (8 GB VRAM).

---

## 5. Activation steering: control vectors через llama.cpp

**Выбрано:** llama.cpp control vectors (PR #5970, смержен) + форк сервера для live-update scale без reload модели.

**Альтернативы:**
- **EasySteer** — построен на vLLM. Отбрасываем вместе с vLLM.
- **Goodfire SAE через Ember API** — облачный, не локальный.
- **Чистые PyTorch hooks через llama-cpp-python** — рабочий fallback, но медленнее.

**Обоснование:**
- Прямое сравнение ([arxiv 2502.16681](https://arxiv.org/pdf/2502.16681)): linear probes / persona vectors дают **88% editing success vs 41% у SAE-probes** на 7B-классе. → persona vectors как primary, SAE отложен в v2 для диагностики.
- Готовый production-генератор: [jukofyork/control-vectors](https://github.com/jukofyork/control-vectors) через eigendecomposition.
- Hot-swap через API ещё не смержен ([Issue #10685](https://github.com/ggml-org/llama.cpp/issues/10685)) — пишем свой endpoint `POST /steering` поверх `llama_control_vector_apply`. Объём работы ~200 строк C++.

**Реализация П2 (концепты как паттерны):**
- Базовый слой: статические persona vectors (характер NPC) — извлекаются один раз через контрастные пары.
- Динамический слой: VAD-тройка через E-STEER-подобный механизм (готовый EmotionVector подходит).
- Условный слой: CAST-логика на стороне Java-клиента — какие scales включать в каком контексте.

«Любовь кузнеца к жене» = композиция: персона-вектор + триггер CAST на присутствие/упоминание жены + VAD-сдвиг + специфические features. Именно «паттерн мелких параметров», как в Принципе 2.

---

## 6. Architecture cycle: трёхуровневая

**Выбрано:**

```
L0 — 20 Hz, Java only:    pathfinding, физика, collision
L1 — 1 Hz, Java:          selective_perception → STM
                          utility-AI: рутина (eat/work/sleep/socialize)
                          if novelty > θ: trigger LLM
L2 — 0.1 Hz, llama.cpp:   thought stream (П4) + diaglogi
                          divergent (slot 2, T=0.9) → convergent (slot 1)
L3 — per игровой день:    sleep consolidation (П3)
                          slot save → rewrite → reload
```

**Обоснование:** 99% действий идут на классическом коде (L0+L1), LLM трогается только при значимости. Это решает риск №1 из ADR-003 (Принцип 4 дорогой по compute) до того как стало стеной.

Триггеры LLM:
1. Novelty trigger — восприятие необъяснимое текущей моделью мира
2. Goal void — план достиг цели или провалился
3. Social trigger — обращение от другого агента
4. Periodic background thought — таймер с jitter, частота f(arousal, idleness)
5. Sleep consolidation — раз за «игровой день»

---

## 7. Memory layer

**Выбрано:**

- **STM:** in-memory структурированный буфер событий дня (LightMem-стиль).
- **LTM:** provenance-tagged beliefs `(content, source, confidence, last_touched, witnessed_at)`.
- **Affect:** VAD (Valence-Arousal-Dominance) + multi-scale (mood / personality drift).
- **Character:** HEXACO (6 осей) + persona-vector scales + attachment patterns.

**JSON для MVP**, не векторная БД. Векторы добавим в v2 когда NPC будет много.

**Источники:** LightMem ([arxiv 2510.18866](https://arxiv.org/html/2510.18866v1)), MIRROR ([arxiv 2506.00430](https://arxiv.org/abs/2506.00430)), provenance tagging ([arxiv 2506.17331](https://arxiv.org/pdf/2506.17331)).

---

## 8. Параметры характера: HEXACO + VAD + лоскутные

**Выбрано:** ~10 ядерных параметров + 8-10 на каждую сильную привязанность ≈ 30-40 для одного NPC.

- **6 осей HEXACO:** Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism, Honesty-Humility. Honesty-Humility критичен для сценариев с обманом ([arxiv 2508.00742](https://arxiv.org/html/2508.00742)).
- **3 оси VAD:** Valence, Arousal, Dominance — текущее эмоциональное состояние.
- **Trust-вектор** к ключевым другим NPC.
- **Лоскутные параметры на привязанность** — внимание, узнавание, тепло, забота, боль-при-отсутствии, ревность, принятие слабостей.

**Не Big Five** (5) — провалится на сценариях с обманом.
**Не тысячи SAE-features** — управление неоперационализировано.

---

## 9. Что НЕ в MVP (отложено явно)

- **Nightly LoRA через STABLE.** STABLE тестировали только 8 итераций ([arxiv 2510.16089](https://arxiv.org/html/2510.16089v1)). Данных о 50+ ночах нет ни у кого. → v2.
- **AriGraph** (полный KG world model). Overkill для одного NPC. → v2.
- **Conceptors** (Boolean-алгебра над концептами). Отложено в v2.
- **Multi-NPC и off-screen симуляция.** Не для MVP.
- **HeLa-Mem / Hebbian** — заманчиво, но добавляет ещё контур обучения. После того как базовая память работает.
- **TTT-E2E** (in-weights memory) — экспериментально, требует custom ядер.

---

## 10. Сводка стека

```
┌─────────────────────────────────────────────────────┐
│  Minecraft Java 1.21.x + Fabric API                 │
│   ├─ PuppetPlayers (server-side FakePlayer)         │
│   └─ Java HTTP client → llama.cpp                   │
│                                                      │
│  llama-server (sidecar, форк с /steering)           │
│   ├─ Qwen2.5-7B-Instruct Q4_K_M (GGUF)              │
│   ├─ --cram 256 --np 2 --slot-save-path            │
│   └─ control vectors (jukofyork-стиль + EmotionVector)│
│                                                      │
│  Memory layer (на JVM)                              │
│   ├─ STM: events-of-day buffer                      │
│   ├─ LTM: provenance-tagged beliefs (JSON)          │
│   ├─ Affect: multi-scale VAD                        │
│   └─ Character: HEXACO + persona scales             │
└─────────────────────────────────────────────────────┘
```

---

## Риски стека (помимо рисков отдельных решений)

**Риск 1: Q4_K_M ослабляет persona vectors.**
Высокая вероятность, средняя серьёзность. Митигация: эксперимент 1 → fallback на Q8_0.

**Риск 2: Forking llama.cpp.**
~200 строк C++ — терпимо, но требует поддержания форка. Митигация: по возможности контрибьютить upstream, минимизировать дельту.

**Риск 3: PuppetPlayers может не поддерживаться на новых версиях.**
Митигация: запинить версию Minecraft 1.21.x, в крайнем случае форкнуть PuppetPlayers.

**Риск 4: GBNF на 7B недостаточно стабилен.**
Митигация: тестируем на эксперименте «Кузнец-нулевой» (см. 05-architecture-v0.md).

---

## Когда пересматривать

- Если эксперимент 1 покажет что Q4_K_M не работает с persona vectors — пересмотреть точность модели.
- Если PuppetPlayers станет недоступным — пересмотреть entity layer.
- Если в v2 потребуется десятки NPC одновременно — рассмотреть переход на vLLM с PagedAttention.
- Если масштабирование до серверной игры — пересмотреть весь стек (это уже не MVP).
