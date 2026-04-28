#!/usr/bin/env bash
# Запуск Mindcraft с конфигом Странника.
# Предполагается что mindcraft-ce склонирован рядом и установлен (npm install).

set -euo pipefail

MINDCRAFT_DIR="${MINDCRAFT_DIR:-../mindcraft-ce}"

if [[ ! -d "$MINDCRAFT_DIR" ]]; then
  echo "Mindcraft не найден: $MINDCRAFT_DIR"
  echo "Поставить:"
  echo "  cd .. && git clone https://github.com/mindcraft-ce/mindcraft-ce"
  echo "  cd mindcraft-ce && npm install"
  exit 1
fi

# Скопировать конфиги Странника в Mindcraft (если нужно)
PROFILE_SRC="$(dirname "$0")/../mindcraft_config/andy_wanderer.json"
PROFILE_DST="$MINDCRAFT_DIR/profiles/andy_wanderer.json"

if [[ -f "$PROFILE_SRC" ]] && [[ ! -f "$PROFILE_DST" ]]; then
  cp "$PROFILE_SRC" "$PROFILE_DST"
  echo "Profile-card скопирована в $PROFILE_DST"
fi

cd "$MINDCRAFT_DIR"

echo "Запуск Mindcraft..."
exec npm start
