# Prototype: Странник-нулевой

Первый рабочий прототип Living NPC. Реализация Шага 1 из плана `05-architecture-v0.md` через стек ADR-006.

**Цель:** увидеть Странника-амнезика живым в реальном Minecraft за 3-7 дней работы.

---

## Архитектура

```
Minecraft 1.21.6
    ↑ player connection
Mindcraft (Node.js + Mineflayer)
    ↓ OpenAI-compatible HTTP
Python middleware (этот код)
    ├─ STM/LTM
    ├─ HEXACO + VAD
    ├─ Cognitive loop
    └─ Sleep consolidation (Шаг 5)
    ↓ HTTP
llama-server (llama.cpp)
    └─ Andy-4 8B Q4_K_M
```

Mindcraft видит middleware как обычный OpenAI API. Внутри middleware идёт наш cognitive cycle с инверсией критерия (ADR-004).

---

## Структура

```
prototype/
├── README.md                    # этот файл
├── requirements.txt             # Python deps
├── middleware/
│   ├── __init__.py
│   ├── server.py               # FastAPI: эмулирует OpenAI /v1/chat/completions
│   ├── llm_client.py           # клиент к llama-server
│   ├── cognitive_loop.py       # основной цикл агента
│   ├── memory.py               # STM/LTM с provenance tags
│   ├── character.py            # HEXACO + VAD
│   ├── prompts.py              # шаблоны промптов
│   └── config.py               # загрузка YAML конфига
├── configs/
│   └── wanderer.yaml           # персона Странника
├── mindcraft_config/
│   ├── settings.js.template    # template для Mindcraft
│   └── andy_wanderer.json      # profile-card Странника
├── scripts/
│   ├── start_llama_server.sh   # запускает llama.cpp
│   ├── start_middleware.sh     # запускает FastAPI
│   └── start_mindcraft.sh      # запускает Mindcraft
└── logs/                       # логи cognitive cycle (gitignored)
```

---

## Setup (high-level)

### 1. Поставить llama.cpp

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp && make GGML_CUDA=1
```

### 2. Скачать Andy-4

```bash
# через HuggingFace
wget https://huggingface.co/Sweaterdog/Andy-4/resolve/main/Andy-4.Q4_K_M.gguf
```

### 3. Запустить llama-server

```bash
./scripts/start_llama_server.sh
# слушает на :8080
```

### 4. Запустить middleware

```bash
pip install -r requirements.txt
./scripts/start_middleware.sh
# слушает на :8090, прокидывает в llama-server :8080
```

### 5. Поставить Mindcraft

```bash
git clone https://github.com/mindcraft-ce/mindcraft-ce
cd mindcraft-ce
npm install
# скопировать mindcraft_config/settings.js.template как settings.js
# скопировать mindcraft_config/andy_wanderer.json в profiles/
```

### 6. Запустить Minecraft 1.21.6 server (vanilla)

В отдельном терминале — обычный Minecraft server.

### 7. Запустить Mindcraft

```bash
./scripts/start_mindcraft.sh
# Странник появится в игре
```

### 8. Подключиться к серверу

Запустить Minecraft client → Multiplayer → localhost.

---

## Что прототип делает (текущая ревизия)

Шаг 1 (текущий):
- ✅ Странник-амнезик подключается к серверу через Mindcraft-бот
- ✅ Реагирует на восприятие через cognitive loop
- ✅ Имеет HEXACO-характер (через промпт, без steering пока)
- ✅ Имеет VAD-эмоциональное состояние
- ✅ Накапливает STM events
- ⏳ LTM пока in-memory, без persistence
- ❌ Sleep consolidation — не в Шаге 1
- ❌ Activation steering — Шаг 3
- ❌ Thought stream — Шаг 4

Подробнее — `06-zero-patient-spec.md` и `05-architecture-v0.md` §9.

---

## Что НЕ работает (известно)

- Persona vectors не подключены — Шаг 3
- LTM не персистентна между сессиями — Шаг 5
- Lifeness Triad метрики не считаются — после Шага 5

---

## Лицензия

TBD (см. главный README проекта).
