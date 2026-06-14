#!/usr/bin/env python3
"""English Dictionary Bot — Entry Point.

Usage:
    Set TELEGRAM_BOT_TOKEN in .env or export it
    python3 main.py

Optional env vars:
    HERMES_API_BASE     (default: http://localhost:8642/v1)
    HERMES_API_KEY      (default: hermes-api-key-local)
    HERMES_MODEL        (default: hermes-agent)
    DB_PATH             (default: ./data/vocab.db)
    ALLOW_ALL           (default: true)
    ALLOWED_USERS       (comma-separated user IDs, used when ALLOW_ALL=false)
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config import TELEGRAM_BOT_TOKEN, dump as dump_config
import database as db
from bot import (
    start,
    handle_word,
    list_words,
    stats,
    export_csv,
    pronunciation_callback,
)


def main():
    # Init database
    print("[init] Initializing database...")
    db.init_db()

    # Print config
    print(f"[init] Config:\n{dump_config()}")

    # Build app
    print("[init] Starting Telegram bot...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_words))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("export", export_csv))

    # Text handler (catch-all for single words) — must be after command handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_word))

    # Callback query handler (pronunciation buttons)
    app.add_handler(CallbackQueryHandler(pronunciation_callback, pattern=r"^tts_"))

    # Start polling
    print("[init] Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()