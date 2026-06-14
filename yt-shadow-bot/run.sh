#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f ~/.hermes/.env ]; then
    set -a
    source ~/.hermes/.env 2>/dev/null || true
    set +a
fi

if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env" 2>/dev/null || true
    set +a
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN is not set."
    exit 1
fi

echo "Starting YouTube Shadowing Bot..."
echo "Language: ${TRANSCRIPT_LANGUAGE:-en}"

exec "$DIR/venv/bin/python3" "$DIR/main.py"