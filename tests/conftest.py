"""conftest.py — pre-register local modules for all bot test files.

Bot source files contain `from config import ...` style intra-package
imports. Since bots are NOT proper Python packages (hyphenated directories),
we must manually populate sys.modules before loading each source module.
"""
import sys
import os
import re
from unittest.mock import MagicMock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _make_mock_module(name, **attrs):
    """Create a mock module and register it in sys.modules."""
    mod = type(sys)(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# ── Mock config for each bot ─────────────────────────────────

def register_know_bot_config():
    _make_mock_module(
        "config",
        TELEGRAM_BOT_TOKEN="mock_token",
        ALLOW_ALL=True,
        ALLOWED_USERS=[],
        GDRIVE_ENABLED=True,
        GDRIVE_FOLDER_NAME="test",
        DATA_DIR="/tmp/know_data",
        DB_PATH="/tmp/know_data/know.db",
        MAX_CONTENT_CHARS=50000,
        HERMES_API_URL="http://localhost:8642/v1",
        HERMES_API_KEY="mock_key",
        LOCAL_LLM_BASE="http://192.168.20.154:11434/v1",
        LOCAL_LLM_API_KEY="mock_key",
        LOCAL_LLM_MODEL="test",
        LOCAL_LLM_ENABLED=False,
        GAPI_VENV="/tmp/gws-env",
        GAPI_SCRIPT="/tmp/google_api.py",
    )


def register_dictionary_bot_config():
    _make_mock_module(
        "config",
        TELEGRAM_BOT_TOKEN="mock_token",
        ALLOW_ALL=True,
        ALLOWED_USERS=[],
        HERMES_API_BASE="http://localhost:8642/v1",
        HERMES_API_KEY="mock_key",
        HERMES_MODEL="test",
        DB_DIR="/tmp",
        DB_PATH="/tmp/vocab.db",
        TTS_LANG="en",
        TTS_TLD_UK="co.uk",
        TTS_TLD_US="com",
        LOCAL_LLM_BASE="http://192.168.20.154:11434/v1",
        LOCAL_LLM_API_KEY="mock_key",
        LOCAL_LLM_MODEL="test",
        LOCAL_LLM_ENABLED=False,
    )


def register_ytd_bot_config():
    _make_mock_module(
        "config",
        TELEGRAM_BOT_TOKEN="mock_token",
        ARCHIVE_DIR="/tmp/archive",
        DEFAULT_QUALITY="720",
        YT_RE=re.compile(
            r"(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/shorts/)"
            r"([a-zA-Z0-9_-]{11})"
        ),
        YTDN_RE=re.compile(r"^ytdn\b", re.IGNORECASE),
        YTDL_RE=re.compile(r"^ytdownload\b", re.IGNORECASE),
        VALID_QUALITIES={"144", "240", "360", "480", "720", "1080", "1440", "2160", "4320"},
        COOKIES_FILE=MagicMock(),
        LOG_FILE="/tmp/test_ytd.log",
    )


def register_yt_shadow_bot_config():
    _make_mock_module(
        "config",
        TELEGRAM_BOT_TOKEN="mock_token",
        ALLOW_ALL=True,
        ALLOWED_USERS=[],
        MAX_MESSAGE_LENGTH=4000,
        TRANSCRIPT_LANGUAGE="en",
    )


def register_telegram_mock():
    """Mock telegram module so bot.py files can import it."""
    if "telegram" not in sys.modules:
        tg = type(sys)("telegram")
        tg.Update = MagicMock()
        tg.InlineKeyboardButton = MagicMock()
        tg.InlineKeyboardMarkup = MagicMock()
        tg.ext = type(sys)("ext")
        tg.ext.Application = MagicMock()
        tg.ext.CommandHandler = MagicMock()
        tg.ext.MessageHandler = MagicMock()
        tg.ext.CallbackQueryHandler = MagicMock()
        tg.ext.filters = MagicMock()
        tg.ext.ContextTypes = MagicMock()
        tg.constants = type(sys)("constants")
        tg.constants.ParseMode = "MARKDOWN"
        sys.modules["telegram"] = tg
        sys.modules["telegram.ext"] = tg.ext
        sys.modules["telegram.constants"] = tg.constants


def register_database_mock():
    if "database" not in sys.modules:
        _make_mock_module("database")


def register_tts_handler_mock():
    if "tts_handler" not in sys.modules:
        _make_mock_module("tts_handler")
