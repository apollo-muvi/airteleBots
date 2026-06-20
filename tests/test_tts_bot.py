"""Placeholder tests for tts-bot.

tts-bot has no pure-logic functions — it's entirely Telegram handlers
and edge-tts subprocess calls. This file verifies the module imports
correctly (with mocked dependencies).
"""
import sys
from unittest.mock import MagicMock, patch
import pytest


def test_tts_bot_imports():
    """Verify tts-bot.py can be imported with mocked deps."""
    # Mock telegram
    mock_tg = type(sys)("telegram")
    mock_tg.Update = MagicMock()
    mock_tg.ext = type(sys)("ext")
    mock_tg.ext.Application = MagicMock()
    mock_tg.ext.CommandHandler = MagicMock()
    mock_tg.ext.MessageHandler = MagicMock()
    mock_tg.ext.filters = MagicMock()
    mock_tg.ext.ContextTypes = MagicMock()
    sys.modules["telegram"] = mock_tg
    sys.modules["telegram.ext"] = mock_tg.ext
    sys.modules["telegram"] = mock_tg

    # Mock dotenv
    mock_dotenv = type(sys)("dotenv")
    mock_dotenv.load_dotenv = MagicMock(return_value=True)
    sys.modules["dotenv"] = mock_dotenv

    # Set env var so bot doesn't crash on startup
    import os
    os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"

    # Now import — should not raise
    from tests.helpers import load_module
    mod = load_module("tts-bot", "tts-bot")
    assert mod is not None
    assert hasattr(mod, "main")