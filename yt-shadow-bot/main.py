#!/usr/bin/env python3
"""YouTube Shadowing Transcript Bot — Entry Point.

Usage:
    Set TELEGRAM_BOT_TOKEN in .env or export it
    python3 main.py

Optional env vars:
    TRANSCRIPT_LANGUAGE     (default: en)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)
from config import TELEGRAM_BOT_TOKEN
from bot import start, handle_message, set_language, toggle_html


def main():
    print("[init] Starting YouTube Shadowing Bot...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lang", set_language))
    app.add_handler(CommandHandler("html", toggle_html))

    # Catch-all for text messages (URLs or commands)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("[init] Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()