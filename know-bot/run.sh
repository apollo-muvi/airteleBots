#!/bin/bash
cd /home/apollo/know-bot
source /home/apollo/know-bot/.venv/bin/activate
export $(cat /home/apollo/know-bot/.env | xargs)
exec python3 /home/apollo/know-bot/main.py