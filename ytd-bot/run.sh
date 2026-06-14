#!/bin/bash
cd /home/apollo/ytd-bot
source /home/apollo/.local/share/virtualenvs/ytd-bot/bin/activate 2>/dev/null || source ytd-bot-env/bin/activate 2>/dev/null || true
export $(cat .env | xargs)
exec python3 bot.py