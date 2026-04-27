# ADR-006: Pivot на Mindcraft + Python middleware

**Статус:** Принято
**Дата:** 2026-04-27
**Контекст сессии:** session 03, разведка путей реализации с учётом 8GB VRAM
**Изменяет:** ADR-005 (см. блок изменений ниже)

---

## Решение

**Стек реализации MVP меняется с «свой Fabric mod + PuppetPlayers + Qwen2.5-7B» на «Mindcraft + Python middleware + Andy-4 (Llama-8B-R1)».**

Это техническое решение, не архитектурное — четыре принципа (ADR-003) и инверсия критерия (ADR-004) остаются неизменными. Меняется только воплощение тела NPC и базовая модель.

---

## Что конкретно меняется

| Компонент | Было (ADR-005) | Стало (ADR-006) |
|---|---|---|
| Тело NPC | PuppetPlayers (Fabric mod) | Mindcraft + Mineflayer (Node.js) |
| Базовая модель | Qwen2.5-7B-Instruct | Andy-4 (Sweaterdog/Andy-4, Llama-8B-R1 fine-tune) |
| Action layer | свой Java behavior tree | 47 готовых действий Mindcraft |
| Когнитивный мозг | свой Java mod | Python middleware (FastAPI, OpenAI-совместимый эндпоинт) |
| Версия Minecraft | Fabric 1.21.x (без уточнения) | 1.21.6 (основная цель Mindcraft) |
| Mindcraft вариант | — | mindcraft-ce (форк с RAG/LanceDB) |
| KV cache | f16 (по умолчанию) | q8_0 (`--cache-type-k q8_0 --cache-type-v q8_0`) |
| Контекст | 8K f16 | 8K q8_0 (~2× эффективности) |
| EmotionVector | готовый для Qwen2.5-7B | надо извлечь заново для Llama-8B-R1 (Шаг 3) |

---

## Почему меняем

### Главная причина — реалистичная оценка времени

Разведка показала разрыв в **3-4 недели работы** между двумя путями:

- ADR-005 путь: написать Fabric mod → setup PuppetPlayers → свой Java action layer → HTTP-клиент → тесты. **3-4 недели до видимого NPC.**
- ADR-006 путь: запустить Mindcraft + llama-server + Python middleware. **3-7 дней до видимого NPC.**

При исследовательском характере проекта это критическая разница. Время до первой обратной связи определяет скорость накопления знаний.

### PuppetPlayers оказался слабее чем казалось

При выборе в ADR-005 не были оценены:
- Всего 67 коммитов, 5 звёзд GitHub
- Никакого HTTP/IPC API — только команды в чате
- Документация — одна страница
- Проект слабо живой

Это рискованная ставка для MVP, особенно когда есть Mindcraft (1661+ коммитов, активно развивается, MIT, релиз 20 марта 2026, MC до 1.21.11).

### Mindcraft закрывает 99% инфраструктуры

То что ADR-005 предписывал писать с нуля:
- ✅ NPC entity (FakePlayer/Mineflayer-bot)
- ✅ Action layer (47 параметризованных действий)
- ✅ Pathfinding (через Mineflayer pathfinder)
- ✅ Perception system (observation queue)
- ✅ Action queue + execution
- ✅ HTTP-клиент к LLM
- ✅ Function calling / tool use
- ✅ Multi-agent infrastructure (для будущего)
- ✅ Persona-карточки + system prompts
- ✅ RAG (через mindcraft-ce + LanceDB)

Всё это уже отлажено и протестировано на локальных моделях. Писать своё — переоткрывать колесо.

### Andy-4 закрывает Minecraft-tuning

Чистый Qwen2.5-7B/Llama-8B не умеют играть в Minecraft из коробки. На исследовательском прототипе это значит «Странник застрял в стене и не понимает что делать». Andy-4 ([Sweaterdog/Andy-4](https://huggingface.co/Sweaterdog/Andy-4)) — Llama-8B-R1 fine-tune специально под Mindcraft. Это даёт нам Minecraft-aware действия с первой минуты.

Цена — потеря готового EmotionVector (он только для Qwen2.5-7B). Извлекать заново для Llama-8B-R1 — плановая работа на Шаге 3, не блокер.

### 8GB VRAM требует точности

При выборе в ADR-005 железо ещё не было известно конкретно. Сейчас ясно: RTX 3060 8GB. Это требует:
- Q4_K_M, не Q8_0 (Q8 7B не помещается с KV cache)
- KV cache в q8_0 для расширения контекста
- Andy-4 (5GB Q4) точнее под этот бюджет, чем размытое «Qwen2.5-7B Q4_K_M»

---

## Архитектура нового стека

```
┌─────────────────────────────────────────────────────────────┐
│  Minecraft Java 1.21.6 server (vanilla)                     │
│       ↑ player connection                                    │
│  Mindcraft (mindcraft-ce, Node.js)                          │
│   ├─ Mineflayer-bot per NPC (один Странник)                 │
│   ├─ 47 действий (move, mine, attack, sleep, chat, ...)     │
│   ├─ observation queue (что NPC видит)                       │
│   └─ LLM client → custom URL                                 │
│        ↓ OpenAI-compatible HTTP                              │
│  Python middleware (FastAPI)                                 │
│   ├─ Эмулирует OpenAI /v1/chat/completions для Mindcraft    │
│   ├─ Внутри — наш cognitive cycle:                          │
│   │     ├─ STM/LTM (provenance-tagged)                      │
│   │     ├─ HEXACO + VAD state                                │
│   │     ├─ Sleep consolidation (П3)                         │
│   │     └─ Thought stream (П4) — Шаг 4                      │
│   └─ Дёргает llama-server                                    │
│        ↓ HTTP                                                │
│  llama-server (llama.cpp, форк со /steering на Шаге 3)      │
│   ├─ Andy-4 8B Q4_K_M (~5 GB)                               │
│   ├─ --cache-type-k q8_0 --cache-type-v q8_0                │
│   ├─ -c 8192 (8K контекста)                                 │
│   ├─ --np 2 (slots: main + thought)                         │
│   └─ control vectors (Шаг 3)                                 │
└─────────────────────────────────────────────────────────────┘
```

**Ключевое разделение ответственности:**
- **Mindcraft** = тело и среда. Не знает о наших принципах, видит только OpenAI-API.
- **Python middleware** = мозг и архитектура. Реализует все четыре принципа + инверсию критерия.
- **llama-server** = языковой субстрат. Глупый, но быстрый.

Это даёт чистый интерфейс: Mindcraft можно заменить на mock-симулятор для unit-тестов когнитивной архитектуры (Path A из 06-zero-patient-spec), не трогая мозг.

---

## Альтернативы, которые мы рассмотрели

**A1. Оставить ADR-005 как есть.**
Отвергнуто: 3-4 недели работы вместо 3-7 дней — недопустимо для исследовательского проекта.

**A2. AIRI framework (moeru-ai/airi).**
Отвергнуто: AIRI богаче (Brain/Ears/Mouth/Body слои, Memory Alaya), но general-purpose, не Minecraft-first. Adaptation layer был бы сравним по объёму с Mindcraft-интеграцией.

**A3. Voyager (MineDojo).**
Отвергнуто: архивный с 2023, не поддерживает локальные модели нормально, GPT-4-only.

**A4. PlayerEngine + свой mod.**
Отвергнуто: PlayerEngine на 1.20.1 Fabric / 1.21.1 NeoForge — не основной 1.21.6, и нужен свой mod вокруг.

**A5. shasankp000/AI-Player.**
Отвергнуто: жёсткая Java-архитектура, RL+Ollama, перепрограммировать под наши принципы сложнее чем взять Mindcraft.

**A6. Mindcraft + Python middleware + Andy-4.** ✅ ВЫБРАНО

---

## Риски нового стека

**R1. Persona vectors на Q4_K_M ослаблены.**
Уже был риск №1 в ADR-005, остаётся. Q4_K_M даёт ~20% потери на instruction-following. Митигация: Шаг 3 — эмпирически проверяем; fallback на Q5_K_M или Q8_0 (если найдём как уместить в 8GB через KV-сжатие).

**R2. EmotionVector надо извлекать заново для Llama-8B-R1.**
~Неделя работы. Митигация: Шаги 1-2 идут без steering, на Шаге 3 параллельно делаем извлечение. Не блокирует MVP-демо.

**R3. Mindcraft по умолчанию — «assistant, играющий в Minecraft», не «человек, живущий».**
Промпты построены под помощника. Митигация: переопределяем системный промпт через конфиг персоны Странника. Если потребуется глубже — форк mindcraft-ce.

**R4. 8K контекста на 8GB — впритык.**
KV q8_0 даёт +50% эффективного контекста. На длинной сессии STM может переполнить — нужна жёсткая дисциплина summarization. Митигация: сон-консолидация (П3) сжимает STM каждый игровой день.

**R5. Зависимость от живости Mindcraft и Andy-4.**
Если проекты заглохнут — нам придётся форкать или переписывать. Митигация: оба MIT, оба активны на апрель 2026, форк не катастрофа.

**R6. Node.js + Python + Java одновременно.**
Стек становится поликультурным. Митигация: чёткие интерфейсы (HTTP/JSON), нет shared state между языками.

---

## Что становится отложенным

- **Свой Fabric mod** — отложено в v2 (если потребуется выйти за рамки Mindcraft).
- **PuppetPlayers** — отложено навсегда; превзойдён Mineflayer-ботами Mindcraft.
- **Qwen2.5-7B** — остаётся как fallback если Andy-4 окажется неподходящим.

---

## Влияние на ADR-005

ADR-005 не отменяется, но дополняется:
- Раздел 1 (Fabric 1.21.x) — уточняется до **1.21.6**.
- Раздел 2 (PuppetPlayers) — заменяется на **Mindcraft + Mineflayer**.
- Раздел 4 (Qwen2.5-7B) — заменяется на **Andy-4** для MVP, Qwen-7B остаётся как backup.
- Раздел 5 (control vectors) — отложен на Шаг 3, требует извлечения для Llama-8B-R1.
- Раздел 10 (сводка стека) — пересматривается.

В файле ADR-005 ставится явная отсылка на ADR-006 в верхней части.

---

## Влияние на 05-architecture-v0.md и 06-zero-patient-spec.md

**05-architecture-v0.md** — план реализации (раздел 9) корректируется:
- Шаг 1 «голый каркас» теперь = «поднять Mindcraft + middleware + Andy-4», не «писать Fabric mod».
- Сроки сокращаются с 1-2 недель до 3-7 дней.

**06-zero-patient-spec.md** — развилка реализации устаревает:
- Путь B (свой Fabric mod) отвергнут.
- Гибрид-Mindcraft становится единственным главным путём.
- Path A (Python mock) остаётся как unit-test среда для cognitive loop.

Обновление этих документов — отдельная задача после того как прототип побежит.

---

## Когда пересматривать

- Если Mindcraft перестанет поддерживать новые версии Minecraft → форк или переход.
- Если Andy-4 окажется непригодным для steering → возврат к Qwen2.5-7B + ручное обучение Minecraft-командам.
- Если Mindcraft-промпты окажется невозможно перепрограммировать под «жителя мира» (assistant-mode слишком вшит) → форк mindcraft-ce с переписанным prompt builder.
- Если 8GB не хватит даже на Andy-4 Q4 + KV q8_0 → апгрейд железа или Q3_K_S.
