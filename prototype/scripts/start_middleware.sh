#!/usr/bin/env bash
# Запуск Python middleware. Перед этим должен быть запущен llama-server.

set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG="${CONFIG:-configs/wanderer.yaml}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8090}"
LOG_LEVEL="${LOG_LEVEL:-info}"

echo "Запуск middleware на ${HOST}:${PORT} с ${CONFIG}"
exec python -m middleware.server \
  --config "$CONFIG" \
  --host "$HOST" \
  --port "$PORT" \
  --log-level "$LOG_LEVEL"
