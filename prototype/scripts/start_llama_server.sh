#!/usr/bin/env bash
# Запуск llama-server с Andy-4 для Странника на RTX 3060 8GB.
# Параметры подобраны под ADR-006: Q4_K_M + KV q8_0 + 8K контекста + 2 слота.

set -euo pipefail

MODEL_PATH="${MODEL_PATH:-./models/Andy-4.Q4_K_M.gguf}"
LLAMA_BIN="${LLAMA_BIN:-./llama.cpp/build/bin/llama-server}"
PORT="${PORT:-8080}"
SLOT_DIR="${SLOT_DIR:-./prototype/logs/slots}"

mkdir -p "$SLOT_DIR"

if [[ ! -f "$MODEL_PATH" ]]; then
  echo "Модель не найдена: $MODEL_PATH"
  echo "Скачать:"
  echo "  wget -O $MODEL_PATH https://huggingface.co/Sweaterdog/Andy-4/resolve/main/Andy-4.Q4_K_M.gguf"
  exit 1
fi

if [[ ! -x "$LLAMA_BIN" ]]; then
  echo "llama-server не найден: $LLAMA_BIN"
  echo "Собрать:"
  echo "  git clone https://github.com/ggml-org/llama.cpp"
  echo "  cd llama.cpp && cmake -B build -DGGML_CUDA=ON && cmake --build build --config Release -j"
  exit 1
fi

echo "Запуск llama-server: Andy-4 Q4_K_M + KV q8_0, контекст 8K, 2 слота"
exec "$LLAMA_BIN" \
  --model "$MODEL_PATH" \
  --port "$PORT" \
  --host 0.0.0.0 \
  --n-gpu-layers 999 \
  --ctx-size 8192 \
  --parallel 2 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --slot-save-path "$SLOT_DIR" \
  --threads 6 \
  --batch-size 512 \
  --ubatch-size 256
