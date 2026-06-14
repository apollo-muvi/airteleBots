#!/usr/bin/env python3
"""中翻英 Bot — translates Chinese to two English styles + TTS audio"""

import os, logging, html, re, asyncio, tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN env var is required")
    raise SystemExit(1)

HERMES_API_BASE = os.getenv("HERMES_API_BASE", "http://localhost:8642/v1")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "hermes-api-key-local")
HERMES_MODEL = os.getenv("HERMES_MODEL", "hermes-agent")

SYSTEM_PROMPT = """You are a professional Chinese-to-English translator.

Given a Chinese text, provide TWO English translations:

1. 【專業版 · Professional】— Formal, professional tone. Suitable for business emails, academic writing, official documents. Use precise vocabulary and proper grammar.

2. 【一般生活用語 · Everyday】— Casual, natural tone. How a native speaker would say it in daily conversation. Use contractions, phrasal verbs, and colloquial expressions.

Format your response EXACTLY like this (with the emoji headers):

📌 專業版
<professional translation here>

🗣 一般生活用語
<everyday translation here>

Only return the two translations. No extra explanations, no Pinyin, no example sentences unless the user explicitly asks."""

from openai import OpenAI


async def generate_tts(text: str, voice: str = "en-US-AriaNeural") -> str | None:
    """Generate TTS audio file using edge-tts. Returns file path or None."""
    try:
        fd, path = tempfile.mkstemp(suffix=".ogg", prefix="tts_")
        os.close(fd)

        proc = await asyncio.create_subprocess_exec(
            "edge-tts", "--voice", voice,
            "--text", text,
            "--write-media", path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=15)
        if proc.returncode == 0 and os.path.getsize(path) > 0:
            return path
        logger.warning(f"TTS failed: returncode={proc.returncode}")
        return None
    except asyncio.TimeoutError:
        logger.warning("TTS timed out")
        return None
    except Exception as e:
        logger.exception(f"TTS error: {e}")
        return None


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 你好！我是中翻英 Bot 🇨🇳→🇬🇧\n\n"
        "傳送中文給我，我會給出 **兩種風格** 的英文翻譯 + 發音！\n\n"
        "📌 專業版 — 正式、適合商業/學術\n"
        "🗣 一般生活用語 — 日常口語、自然\n\n"
        "例如輸入「天氣很好」：\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📌 專業版\n"
        "The weather is very pleasant today.\n\n"
        "🗣 一般生活用語\n"
        "The weather's nice!\n"
        "━━━━━━━━━━━━━━━━━━"
    )


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text or text.startswith("/"):
        return

    user = update.effective_user
    logger.info(f"Translation request from {user.id}: {text[:50]}...")

    try:
        # 1. Get translations
        client = OpenAI(api_key=HERMES_API_KEY, base_url=HERMES_API_BASE)
        response = client.chat.completions.create(
            model=HERMES_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            max_tokens=500,
            timeout=30,
        )

        reply = response.choices[0].message.content or "(無回應)"

        # 2. Extract English sentences for TTS
        # Parse: 📌 專業版\n...\n\n🗣 一般生活用語\n...
        parts = re.split(r'📌\s*專業版|🗣\s*一般生活用語', reply)
        prof_text = ""
        casual_text = ""

        for i, p in enumerate(parts):
            p = p.strip().strip('\n')
            # Find which section this belongs to by position in the original reply
            idx_in_reply = reply.find(p)
            prefix = reply[max(0, idx_in_reply - 30):idx_in_reply] if idx_in_reply >= 0 else ""

            if '專業版' in prefix or ('📌' in prefix and i > 0):
                prof_text = p
            elif '一般' in prefix or ('🗣' in prefix):
                casual_text = p

        # Fallback: first non-empty is professional, second is casual
        non_empty = [p for p in parts if p.strip()]
        if not prof_text and len(non_empty) >= 1:
            prof_text = non_empty[0]
        if not casual_text and len(non_empty) >= 2:
            casual_text = non_empty[1]
        # If only one part, it's both
        if not casual_text and prof_text:
            casual_text = prof_text

        logger.info(f"TTS texts — prof: '{prof_text[:40]}' casual: '{casual_text[:40]}'")

        # 3. Send text reply
        await update.message.reply_text(html.escape(reply))

        # 4. Generate and send TTS audio (parallel)
        prof_audio, casual_audio = await asyncio.gather(
            generate_tts(prof_text),
            generate_tts(casual_text),
        )

        # Send audio files as voice messages
        if prof_audio:
            await update.message.reply_voice(voice=open(prof_audio, "rb"), caption="📌 專業版")
            os.unlink(prof_audio)
        if casual_audio:
            await update.message.reply_voice(voice=open(casual_audio, "rb"), caption="🗣 一般生活用語")
            os.unlink(casual_audio)

    except Exception as e:
        logger.exception("Translation error")
        await update.message.reply_text(f"❌ 翻譯失敗：{html.escape(str(e)[:200])}")


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Translate bot (中翻英 + TTS) starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
