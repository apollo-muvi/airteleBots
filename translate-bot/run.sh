#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env" 2>/dev/null || true
    set +a
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN is not set."
    exit 1
fi

echo "Starting Translate Bot (中翻英)..."
exec "$DIR/venv/bin/python3" "$DIR/bot.py"