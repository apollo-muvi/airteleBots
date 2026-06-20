"""Placeholder tests for translate-bot.

translate-bot has no pure-logic functions — it's entirely Telegram
handlers + OpenAI API + edge-tts subprocess. This test verifies
the module can be imported (with mocked deps).
"""
import sys
from unittest.mock import MagicMock
import pytest


def test_translate_bot_imports():
    """Verify translate-bot/bot.py can be imported with mocked deps."""
    import os
    os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"

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

    # Mock openai
    mock_openai = type(sys)("openai")
    mock_openai.OpenAI = MagicMock()
    sys.modules["openai"] = mock_openai

    from tests.helpers import load_module
    mod = load_module("translate-bot", "bot")
    assert mod is not None
    assert hasattr(mod, "main")
    assert hasattr(mod, "generate_tts")