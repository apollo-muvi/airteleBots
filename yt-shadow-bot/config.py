"""Configuration for YouTube Shadowing Transcript Bot."""

import os
from pathlib import Path

# Auto-load .env if present
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN env var is required")

# Transcript
TRANSCRIPT_LANGUAGE = os.environ.get("TRANSCRIPT_LANGUAGE", "en")
MAX_MESSAGE_LENGTH = 4000  # Telegram single message limit minus safety margin
SPLIT_THRESHOLD = 3500     # Split transcript if exceeds this many chars

# When transcript exceeds 10 chunks, auto-export as HTML
HTML_EXPORT_THRESHOLD = 3   # chunks threshold — if _split_text returns > N, export