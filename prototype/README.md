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

## Setup на Windows (рекомендуется — проще)

Стек: **Ollama** (вместо llama.cpp напрямую) + **Python middleware** + **Mindcraft** + **Minecraft 1.21.6 server**.

Ollama — это обёртка вокруг llama.cpp с автоматической установкой и управлением моделями. Под капотом использует тот же llama.cpp; для Шага 1 разницы нет. Для Шага 3 (control vectors) при необходимости перейдём на llama.cpp напрямую.

### 1. Поставить Ollama
- Скачать: https://ollama.com/download/windows
- Установить (next-next-next), Ollama сама стартует в фоне на `localhost:11434`

### 2. Скачать Andy-4
В cmd или PowerShell:
```cmd
ollama pull Sweaterdog/Andy-4
```
~5 GB. Проверить:
```cmd
ollama run Sweaterdog/Andy-4 "Hello"
```
(Ctrl+C для выхода)

### 3. Поставить Python 3.11+ и Node.js LTS
- Python: https://www.python.org/downloads/ (галочку «Add Python to PATH»)
- Node.js: https://nodejs.org/en/download

### 4. Поставить Mindcraft
```cmd
cd C:\Users\sushk\Downloads
git clone https://github.com/mindcraft-ce/mindcraft-ce
cd mindcraft-ce
npm install
```
Скопировать настройки:
```cmd
copy ..\living-npcs\prototype\mindcraft_config\settings.js.template settings.js
copy ..\living-npcs\prototype\mindcraft_config\andy_wanderer.json profiles\andy_wanderer.json
```

### 5. Запустить Minecraft 1.21.6 server (vanilla)
- Скачать server.jar для 1.21.6 с https://www.minecraft.net/en-us/download/server
- В новой папке запустить, принять EULA (`eula=true` в `eula.txt`)
- В `server.properties` поставить `online-mode=false` (для offline-режима Mindcraft)

### 6. Три терминала параллельно

**Терминал 1 — проверка Ollama:**
```cmd
cd C:\Users\sushk\Downloads\living-npcs\prototype
scripts\windows\check_ollama.bat
```

**Терминал 2 — middleware:**
```cmd
cd C:\Users\sushk\Downloads\living-npcs\prototype
scripts\windows\start_middleware.bat
```

**Терминал 3 — Mindcraft:**
```cmd
cd C:\Users\sushk\Downloads\living-npcs\prototype
scripts\windows\start_mindcraft.bat
```

### 7. Запустить Minecraft client
- Версия 1.21.6
- Multiplayer → Direct Connection → `localhost:25565`
- Странник должен появиться в игре

---

## Setup на Linux/Mac (через llama.cpp напрямую)

Используется когда нужны slot save/restore или control vectors (Шаги 3-5).

### 1. Поставить llama.cpp
```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp && cmake -B build -DGGML_CUDA=ON && cmake --build build --config Release -j
```

### 2. Скачать Andy-4
```bash
mkdir models
wget -O models/Andy-4.Q4_K_M.gguf https://huggingface.co/Sweaterdog/Andy-4/resolve/main/Andy-4.Q4_K_M.gguf
```

### 3. Изменить wanderer.yaml
В `configs/wanderer.yaml` поменять `base_url` на `http://localhost:8080`.

### 4. Три терминала
```bash
./scripts/start_llama_server.sh    # llama-server :8080
./scripts/start_middleware.sh      # middleware :8090
./scripts/start_mindcraft.sh       # Mindcraft → Minecraft
```

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
