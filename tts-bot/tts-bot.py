#!/usr/bin/env python3
import asyncio
import os
import tempfile
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Load from environment ──
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN env var is required")
    raise SystemExit(1)

AUDIO_DIR = os.path.expanduser("~/tts-audio")
MAX_TEXT_LEN = 500
os.makedirs(AUDIO_DIR, exist_ok=True)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "你好！傳文字給我，我幫你轉成語音。\n\n"
        "用法：直接傳送文字，或傳送 SSML XML 檔案\n"
        "支援中文語音，可調整語速/音調（用 SSML 格式）"
    )

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        return

    user = update.effective_user
    logger.info(f"TTS request from {user.id} ({user.username}): {text[:50]}...")

    if len(text) > MAX_TEXT_LEN:
        await update.message.reply_text(f"文字太長了，最多 {MAX_TEXT_LEN} 個字")
        return

    try:
        fd, path = tempfile.mkstemp(suffix=".mp3", dir=AUDIO_DIR)
        os.close(fd)

        if text.startswith("<speak"):
            cmd = ["edge-tts", "--ssml", text, "--voice", "zh-CN-XiaoxiaoNeural", "--write-media", path]
        else:
            cmd = ["edge-tts", "--text", text, "--voice", "zh-CN-XiaoxiaoNeural", "--write-media", path]

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(f"edge-tts failed: {stderr.decode()}")
            await update.message.reply_text(f"語音生成失敗：{stderr.decode()[:200]}")
            if os.path.exists(path):
                os.remove(path)
            return

        with open(path, "rb") as f:
            await update.message.reply_voice(voice=f, caption="語音已生成")
        os.remove(path)

    except Exception as e:
        logger.exception("TTS error")
        await update.message.reply_text(f"發生錯誤：{str(e)[:200]}")

async def handle_ssml_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    file = update.message.document
    if not file.file_name.endswith((".xml", ".ssml")):
        await update.message.reply_text("請上傳 .xml 或 .ssml 檔案")
        return

    fd, local_path = tempfile.mkstemp(suffix=".xml", dir=AUDIO_DIR)
    os.close(fd)

    try:
        tg_file = await file.get_file()
        await tg_file.download_to_drive(local_path)

        fd2, out_path = tempfile.mkstemp(suffix=".mp3", dir=AUDIO_DIR)
        os.close(fd2)

        cmd = ["edge-tts", "--ssml", local_path, "--voice", "zh-CN-XiaoxiaoNeural", "--write-media", out_path]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            await update.message.reply_text(f"語音生成失敗：{stderr.decode()[:200]}")
        else:
            with open(out_path, "rb") as f:
                await update.message.reply_voice(voice=f, caption="SSML 語音已生成")
            os.remove(out_path)

    except Exception as e:
        await update.message.reply_text(f"錯誤：{str(e)[:200]}")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

async def handle_audio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("請傳文字給我轉語音，或上傳 SSML/XML 檔案")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.FileExtension("xml") | filters.Document.FileExtension("ssml"), handle_ssml_file))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
    logger.info("TTS bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
