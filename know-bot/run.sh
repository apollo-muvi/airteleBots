#!/bin/bash
cd /home/apollo/airteleBots/know-bot
source /home/apollo/airteleBots/know-bot/.venv/bin/activate
set -a
source /home/apollo/airteleBots/know-bot/.env
set +a
exec python3 /home/apollo/airteleBots/know-bot/main.py