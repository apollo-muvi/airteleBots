#!/usr/bin/env bash
# Run ApolloEW_bot - English Dictionary Bot
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

# Source .env with export
if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env" 2>/dev/null || true
    set +a
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN is not set."
    exit 1
fi

echo "Starting ApolloEW_bot..."
exec "$DIR/venv/bin/python3" "$DIR/main.py"