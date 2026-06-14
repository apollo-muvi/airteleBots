#!/home/apollo/ytd-bot-env/bin/python3
"""YT Download Bot — downloads YouTube videos to ~/2026ytdn/"""

import asyncio, os, re, subprocess, sys, html
from pathlib import Path

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ARCHIVE_DIR = Path(os.environ.get("ARCHIVE_DIR", str(Path.home() / "2026ytdn")))
COOKIES_FILE = Path.home() / "nextjs_space" / "uploads" / "cookies.txt"
DEFAULT_QUALITY = os.environ.get("DEFAULT_QUALITY", "720")

YT_RE = re.compile(
    r'(https?://)?(www\.|m\.)?(youtube\.com|youtu\.be)',
    re.IGNORECASE,
)
# Also match "ytdn <url>" or "ytdownload <url>" commands
YTDN_RE = re.compile(r'^ytdn\s', re.IGNORECASE)
YTDL_RE = re.compile(r'^ytdownload\s', re.IGNORECASE)

ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def build_args(url: str, quality: str = DEFAULT_QUALITY) -> list[str]:
    args = [
        "yt-dlp",
        "--no-playlist",
        "--no-warnings",
        "--newline",
        "-f",
        f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}]/best",
        "--merge-output-format", "mp4",
        "-o", str(ARCHIVE_DIR / "%(title)s.%(ext)s"),
    ]
    if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0:
        args += ["--cookies", str(COOKIES_FILE)]
    args.append(url)
    return args


async def download(url: str, quality: str = DEFAULT_QUALITY) -> tuple[bool, str]:
    args = build_args(url, quality)
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode == 0:
        return True, ""
    else:
        err = stderr.decode(errors="replace").strip()
        msg = err.split("\n")[-1] if err else "下載失敗"
        return False, msg


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    # Support: bare YouTube URL, "ytdn <url>", "ytdownload <url>"
    url_in_text = text
    if YTDN_RE.match(text) or YTDL_RE.match(text):
        # Strip the command prefix to get the actual URL
        url_in_text = YTDN_RE.sub("", text).strip() if YTDN_RE.match(text) else YTDL_RE.sub("", text).strip()

    if not YT_RE.search(url_in_text):
        return

    # Extract the actual YouTube URL
    urls = re.findall(r'(https?://\S+)', url_in_text)
    yt_url = None
    for u in urls:
        if YT_RE.search(u):
            yt_url = u
            break

    if not yt_url:
        yt_url = url_in_text if "youtu" in url_in_text else None
    if not yt_url:
        return

    # Send acknowledgment before starting download
    await update.message.reply_text("📥 收到下載需求，處理中...")

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    success, err_msg = await download(yt_url)

    if success:
        await update.message.reply_text("✅ 下載完成")
    else:
        await update.message.reply_text(f"❌ {html.escape(err_msg)}")


def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN 環境變數未設定")
        sys.exit(1)

    app = Application.builder().token(TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).pool_timeout(30).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("ytd-bot running... polling Telegram", flush=True)
    app.run_polling(allowed_updates=["messages"])


if __name__ == "__main__":
    main()