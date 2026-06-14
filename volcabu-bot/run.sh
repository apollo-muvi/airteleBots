#!/usr/bin/env bash
# Run the English Dictionary Bot
# Usage: ./run.sh

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

# Source Hermes .env (for TELEGRAM_BOT_TOKEN)
if [ -f ~/.hermes/.env ]; then
    set -a
    source ~/.hermes/.env 2>/dev/null || true
    set +a
fi

# Source bot-specific .env (overrides)
if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env" 2>/dev/null || true
    set +a
fi

# Ensure TELEGRAM_BOT_TOKEN is set
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN is not set."
    echo "Create $DIR/.env with:"
    echo 'TELEGRAM_BOT_TOKEN="your_bot_token"'
    exit 1
fi

echo "Starting English Dictionary Bot..."
echo "Hermes API: ${HERMES_API_BASE:-http://localhost:8642/v1}"
echo "Model: ${HERMES_MODEL:-hermes-agent}"

exec "$DIR/venv/bin/python3" "$DIR/main.py"