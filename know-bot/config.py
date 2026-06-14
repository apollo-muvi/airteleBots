"""
Know_Bot Configuration.

All values from environment variables.
"""
import os
import json

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN env var is required")

# Allowed users
ALLOWED_USERS = [u.strip() for u in os.environ.get("ALLOWED_USERS", "").split(",") if u.strip()]
ALLOW_ALL = os.environ.get("ALLOW_ALL", "true").lower() == "true"

# Storage
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "know.db")

# Google Drive
GDRIVE_ENABLED = os.environ.get("GDRIVE_ENABLED", "true").lower() == "true"
GDRIVE_FOLDER_NAME = os.environ.get("GDRIVE_FOLDER_NAME", "Know_Bot_Knowledge")
GAPI_VENV = "/tmp/gws-env"
GAPI_SCRIPT = os.path.expanduser("~/.hermes/skills/productivity/google-workspace/scripts/google_api.py")

# Content fetching
MAX_CONTENT_CHARS = 50000  # max content length to store

def dump():
    return json.dumps({
        "DATA_DIR": DATA_DIR,
        "DB_PATH": DB_PATH,
        "GDRIVE_ENABLED": GDRIVE_ENABLED,
        "GDRIVE_FOLDER_NAME": GDRIVE_FOLDER_NAME,
        "ALLOW_ALL": ALLOW_ALL,
        "ALLOWED_USERS": ALLOWED_USERS,
    }, indent=2, ensure_ascii=False)