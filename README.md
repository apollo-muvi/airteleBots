# AirteleBots 🤖

A monorepo for a suite of Telegram bots running on a headless Linux server.

## Bots

| Bot | Directory | Description |
|:---|:---|:---|
| 📥 **ytd-bot** | `ytd-bot/` | YouTube Video Downloader (@ytdownl539_bot) |
| 🧠 **Know_Bot** | `know-bot/` | Knowledge Storage Bot — save web articles to HTML + Google Drive (@Know_bot) |
| 📖 **Volcabu_Bot** | `volcabu-bot/` | English Dictionary v1 with vocabulary tracking (@Volcabu_bot) |
| 📖 **ApolloEW_Bot** | `apolloew-bot/` | English Dictionary v2 with enhanced features (@ApolloEW_bot) |
| 🌐 **Translate Bot** | `translate-bot/` | Chinese→English translation bot (@Ecche_bot) |
| 🎬 **YT Shadow Bot** | `yt-shadow-bot/` | YouTube Transcript Extractor for shadowing practice |
| 🗣 **TTS Bot** | `tts-bot/` | Text-to-Speech bot using edge-tts |

## Setup

1. Copy `.env.example` to `.env` and fill in your bot tokens
2. Each bot has `requirements.txt` — install deps with:
   ```bash
   pip install -r <bot>/requirements.txt
   ```
3. Run with:
   ```bash
   cd <bot> && python3 main.py
   ```

## Security

- **No tokens in code** — all tokens loaded from `.env` via `os.environ`
- `.env` files are excluded from git via `.gitignore`
- Each bot has its own `.env.example` as a template

## Server Architecture

- All bots run as **systemd user services** on a headless Linux server
- Hermes Agent API (port 8642) serves as unified LLM backend
- Cloudflare tunnels provide HTTPS access (webui.rain0425.com, ssh.rain0425.com)
- Know_Bot integrates with Google Drive for cloud backup