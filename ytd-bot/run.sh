#!/bin/bash
cd /home/apollo/airteleBots/ytd-bot
source /home/apollo/.local/share/virtualenvs/ytd-bot/bin/activate 2>/dev/null || source /home/apollo/ytd-bot-env/bin/activate 2>/dev/null || true
set -a
source /home/apollo/airteleBots/ytd-bot/.env
set +a
exec python3 /home/apollo/airteleBots/ytd-bot/bot.py