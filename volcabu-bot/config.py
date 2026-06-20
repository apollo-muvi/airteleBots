"""Configuration for English Dictionary Bot.

All values come from environment variables.
Set them before running the bot, or create a .env file.
"""

import os
import json

# ── Telegram ──
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN env var is required")

# ── Hermes API Server ──
HERMES_API_BASE = os.getenv("HERMES_API_BASE", "http://localhost:8642/v1")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "hermes-api-key-local")
HERMES_MODEL = os.getenv("HERMES_MODEL", "hermes-agent")

# ── Database ──
DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.getenv("DB_PATH", os.path.join(DB_DIR, "vocab.db"))

# ── TTS ──
TTS_LANG = os.getenv("TTS_LANG", "en")
TTS_TLD_UK = os.getenv("TTS_TLD_UK", "co.uk")
TTS_TLD_US = os.getenv("TTS_TLD_US", "com")

# ── Allowed users ──
ALLOWED_USERS = [u.strip() for u in os.getenv("ALLOWED_USERS", "").split(",") if u.strip()]
ALLOW_ALL = os.getenv("ALLOW_ALL", "true").lower() == "true"

# ── Export config for debugging ──
def dump():
    return json.dumps({
        "HERMES_API_BASE": HERMES_API_BASE,
        "HERMES_MODEL": HERMES_MODEL,
        "DB_PATH": DB_PATH,
        "ALLOWED_USERS": ALLOWED_USERS,
        "ALLOW_ALL": ALLOW_ALL,
    }, indent=2)

# ── Local LLM on Idea3 (192.168.20.154) ──
LOCAL_LLM_BASE = os.getenv('LOCAL_LLM_BASE', 'http://192.168.20.154:11434/v1')
LOCAL_LLM_API_KEY = os.getenv('LOCAL_LLM_API_KEY', 'ollama')
LOCAL_LLM_MODEL = os.getenv('LOCAL_LLM_MODEL', 'hermes-local')
LOCAL_LLM_ENABLED = os.getenv('LOCAL_LLM_ENABLED', 'true').lower() == 'true'
