#!/home/apollo/airteleBots/ytd-bot/venv/bin/python3
"""YT Download Bot — downloads YouTube videos/audio to ~/2026ytdn/"""

import asyncio, os, re, sys, html, subprocess
from pathlib import Path

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ARCHIVE_DIR = Path(os.environ.get("ARCHIVE_DIR", str(Path.home() / "2026ytdn")))
COOKIES_FILE = Path.home() / "2026ytdn" / "cookies.txt"
DEFAULT_QUALITY = os.environ.get("DEFAULT_QUALITY", "720")
DOWNLOAD_TIMEOUT = int(os.environ.get("DOWNLOAD_TIMEOUT", "600"))
TELEGRAM_FILE_LIMIT = 20 * 1024 * 1024  # 20MB soft limit (Telegram receive limit)

YT_RE = re.compile(
    r'(https?://)?(www\.|m\.)?(youtube\.com|youtu\.be)',
    re.IGNORECASE,
)
YTDN_RE = re.compile(r'^ytdn\s', re.IGNORECASE)
YTDL_RE = re.compile(r'^ytdownload\s', re.IGNORECASE)

VALID_QUALITIES = {"144", "240", "360", "480", "720", "1080", "1440", "2160", "4320"}

ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path.home() / "2026ytdn" / "bot-debug.log"


def log_debug(msg: str):
    """Write debug line to log file."""
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


def parse_quality(text: str) -> tuple[str | None, str, str, bool]:
    """Parse YouTube URL, quality, type, and --send flag from message text."""
    rest = text
    if YTDN_RE.match(text):
        rest = YTDN_RE.sub("", text).strip()
    elif YTDL_RE.match(text):
        rest = YTDL_RE.sub("", text).strip()

    urls = re.findall(r'(https?://\S+)', rest)
    yt_url = None
    for u in urls:
        if YT_RE.search(u):
            yt_url = u.rstrip(".,;:!?）)」』")
            break

    if not yt_url:
        if "youtu" in rest:
            yt_url = rest.split()[0] if rest.split() else rest
        else:
            return None, DEFAULT_QUALITY, "video", False

    remaining = rest.replace(yt_url, "", 1).strip()
    quality = DEFAULT_QUALITY
    download_type = "video"
    send_file = False

    if remaining:
        # Check for audio mode
        if re.search(r'\b(?:audio|mp3|m4a|music|only\s*audio)\b', remaining, re.IGNORECASE):
            download_type = "audio"

        # Parse --dpi:X (e.g. --dpi:1080, --dpi:720) — highest priority
        dpi_match = re.search(r'--dpi[=:](\d+|best)\b', remaining, re.IGNORECASE)
        if dpi_match:
            q = dpi_match.group(1).lower()
            if q == "best" or q in VALID_QUALITIES:
                quality = q

        # Fallback: bare number like "1080" or "1080p" (old style)
        if not dpi_match:
            quality_match = re.search(r'\b(\d{3,4})p?\b', remaining)
            if quality_match:
                q = quality_match.group(1)
                if q in VALID_QUALITIES:
                    quality = q
            if re.search(r'\bbest\b', remaining, re.IGNORECASE):
                quality = "best"

        # Parse --send flag
        if re.search(r'--send\b', remaining, re.IGNORECASE):
            send_file = True

    return yt_url, quality, download_type, send_file


def build_args(url: str, quality: str, download_type: str) -> list[str]:
    node_candidates = [
        '/usr/local/bin/node',
        '/home/apollo/.local/bin/node',
        '/usr/bin/node',
        '/usr/local/nvm/versions/node/v22.14.0/bin/node',
        '/home/apollo/.nvm/versions/node/v24.15.0/bin/node',
    ]
    node_path = 'node'
    for p in node_candidates:
        if os.path.exists(p):
            node_path = p
            break

    args = [
        "yt-dlp",
        "--no-playlist",
        "--no-warnings",
        "--newline",
        "--js-runtimes", f"node:{node_path}",
    ]

    if download_type == "audio":
        args.extend(["-x", "--audio-format", "mp3", "--audio-quality", "192k"])
    else:
        if quality == "best":
            format_spec = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        else:
            format_spec = (
                f"bestvideo[height<={quality}][ext=mp4]"
                f"+bestaudio[ext=m4a]/best[height<={quality}]/best"
            )
        args.extend(["-f", format_spec, "--merge-output-format", "mp4"])

    # Trim title at the first pipe (| or ｜) to avoid filename-too-long errors
    args.extend(["--replace-in-metadata", "title", r"[|｜].*", ""])
    args.extend(["-o", str(ARCHIVE_DIR / "%(title)s.%(ext)s")])
    # Hard safety limit: 60 chars max filename (handles Chinese UTF-8 ~180 bytes)
    args.extend(["--trim-filenames", "60"])

    if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0:
        args.extend(["--cookies", str(COOKIES_FILE)])

    args.append(url)
    return args


def extract_filepath(output: str) -> str:
    """Extract final file path from yt-dlp stdout/stderr output."""
    # Merged file (e.g. [Merger] Merging formats into "/path/to/file.mp4")
    merger = re.search(r'\[Merger\] Merging formats into "([^"]+)"', output)
    if merger:
        return merger.group(1)
    # Single download (e.g. [download] Destination: /path/to/file.mp4)
    dests = re.findall(r'\[download\] Destination:\s*"?([^"\n]+)"?', output)
    if dests:
        return dests[-1]
    return ""


def download_sync(url: str, quality: str, download_type: str) -> tuple[bool, str, str]:
    """Run yt-dlp synchronously. Returns (success, error_msg, filepath)."""
    args = build_args(url, quality, download_type)
    log_debug(f"Starting: {' '.join(args)}")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=DOWNLOAD_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        log_debug("Timeout expired")
        return False, "⏱ 下載超時（超過10分鐘），請稍後再試或使用較低畫質", ""
    except FileNotFoundError:
        log_debug("yt-dlp not found")
        return False, "❌ yt-dlp 未安裝", ""
    except Exception as e:
        log_debug(f"Exception: {e}")
        return False, f"❌ 下載失敗：{e}", ""

    log_debug(f"Exit code: {result.returncode}")
    output = (result.stdout or "") + (result.stderr or "")

    if result.returncode == 0:
        filepath = extract_filepath(output)
        log_debug(f"Downloaded file: {filepath}")
        return True, "", filepath
    else:
        err_text = result.stderr.strip() if result.stderr else output.strip()
        err_lower = err_text.lower()

        if "sign in" in err_lower or "login" in err_lower or "age" in err_lower:
            return False, "🔒 此影片需要登入或年齡驗證，請上傳 cookies.txt", ""
        elif "copyright" in err_lower or "blocked" in err_lower:
            return False, "🚫 此影片因版權或地區限制無法下載", ""
        elif "private" in err_lower:
            return False, "🔒 此影片為私人影片", ""
        elif "unavailable" in err_lower or "not available" in err_lower:
            return False, "❌ 此影片無法存取或已被移除", ""
        elif "ffmpeg" in err_lower and ("not found" in err_lower or "not installed" in err_lower):
            return False, "⚠️ ffmpeg 未安裝，無法合併影片/音訊", ""
        elif "http error 403" in err_lower:
            return False, "🔒 存取被拒（HTTP 403），可能需要 cookies 或 VPN", ""

        lines = [
            l.strip() for l in err_text.split("\n")
            if l.strip() and "WARNING" not in l.upper()
        ]
        msg = lines[-1] if lines else "下載失敗"
        return False, f"❌ {html.escape(msg[:200])}", ""


async def send_file_to_telegram(update: Update, filepath: str):
    """Send downloaded file to the user via Telegram."""
    if not os.path.exists(filepath):
        await update.message.reply_text(f"❌ 檔案不存在：{filepath}")
        return

    size = os.path.getsize(filepath)
    fname = Path(filepath).name

    if size > TELEGRAM_FILE_LIMIT:
        await update.message.reply_text(
            f"📁 檔案過大 ({size / 1024 / 1024:.0f}MB)，Telegram 限制 50MB\n"
            f"📂 位置：{filepath}"
        )
        return

    ext = Path(filepath).suffix.lower()
    try:
        with open(filepath, "rb") as f:
            if ext in (".mp4", ".webm", ".mkv", ".avi", ".mov"):
                await update.message.reply_video(
                    f, caption=f"✅ {fname}",
                    read_timeout=120, write_timeout=120,
                )
            elif ext in (".mp3", ".m4a", ".wav", ".ogg", ".aac"):
                await update.message.reply_audio(
                    f, caption=f"✅ {fname}",
                    read_timeout=120, write_timeout=120,
                )
            else:
                await update.message.reply_document(
                    f, caption=f"✅ {fname}",
                    read_timeout=120, write_timeout=120,
                )
    except Exception as e:
        await update.message.reply_text(
            f"❌ 傳送失敗：{e}\n📂 位置：{filepath}"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    log_debug(f"Received: {text[:100]}")

    is_ytdn_cmd = bool(YTDN_RE.match(text) or YTDL_RE.match(text))
    has_yt_url = bool(YT_RE.search(text))

    if not is_ytdn_cmd and not has_yt_url:
        return

    yt_url, quality, download_type, send_file = parse_quality(text)
    if not yt_url or not YT_RE.search(yt_url):
        log_debug(f"No URL found in: {text}")
        return

    type_icon = "🎵" if download_type == "audio" else "🎬"
    type_label = "音訊" if download_type == "audio" else "影片"
    quality_label = quality + ("p" if quality != "best" else "")
    extras = []
    if send_file:
        extras.append("📤 傳送")
    extras_str = f" | {' '.join(extras)}" if extras else ""

    desc = (
        f"📥 收到下載需求\n"
        f"{type_icon} {type_label} | 畫質: {quality_label}{extras_str}\n"
        f"⏳ 處理中..."
    )
    await update.message.reply_text(desc)
    log_debug(f"Sent acknowledgment, starting download for {yt_url[:60]}...")

    # Run sync download in executor to not block the event loop
    loop = asyncio.get_running_loop()
    success, err_msg, filepath = await loop.run_in_executor(
        None, download_sync, yt_url, quality, download_type,
    )
    log_debug(f"Download result: success={success}, filepath={filepath}")

    if success:
        if send_file and filepath:
            await send_file_to_telegram(update, filepath)
        else:
            await update.message.reply_text(f"✅ 下載完成！已存至 {ARCHIVE_DIR}")
    else:
        await update.message.reply_text(err_msg)


def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN 環境變數未設定")
        sys.exit(1)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_debug("=== ytd-bot started ===")

    app = (
        Application.builder()
        .token(TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("ytd-bot running... polling Telegram", flush=True)
    app.run_polling(allowed_updates=["messages"])


if __name__ == "__main__":
    main()