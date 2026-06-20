"""
Know_Bot — Save knowledge shared via Telegram to HTML + Google Drive.

Usage:
    Set TELEGRAM_BOT_TOKEN in .env or export it
    python3 main.py
"""
import sys
import os
import re
from datetime import datetime
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, ALLOW_ALL, ALLOWED_USERS, GDRIVE_ENABLED, dump as dump_config
import config
import database as db
import html_generator
from html_generator import verify_formatting
from content_fetcher import is_url, fetch_url_content, extract_domain, generate_article_id, extract_url
import gdrive_sync
from inference import ask_hermes

# ── Auth ──

def _is_authorized(user_id: int) -> bool:
    if ALLOW_ALL:
        return True
    return str(user_id) in ALLOWED_USERS


# ── Handlers ──

async def start(update: Update, context):
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ 你沒有使用這個 bot 的權限。")
        return

    welcome = (
        "📚 *Know_Bot* — 知識儲存助手\n\n"
        "把我加入 Telegram 的「分享」選單，看到值得深入研究的內容就分享給我！\n\n"
        "🔹 *支援格式*\n"
        "  🔗 網頁連結 → 自動抓取標題 + 摘要 + 內文\n"
        "  📝 純文字   → 直接儲存\n"
        "  ❓ 技術問題 → `/ask` 自動推理更正並產出歸納\n\n"
        "🔹 *指令*\n"
        "  `/list`     — 最近儲存的知識\n"
        "  `/stats`    — 知識庫統計\n"
        "  `/search`   — 搜尋知識庫（例如 `/search OpenClaw`）\n"
        "  `/ask`      — 技術問答（例如 `/ask 什麼是 interface providers？`）\n\n"
        "🔹 *範例*\n"
        "  分享一個網址給 bot → 自動存成精美 HTML + 同步到 Google Drive\n"
        "  或輸入 `/ask inference providers 跟 OpenAI 有什麼差別？`"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context):
    """Handle a shared message — URL or plain text."""
    if not _is_authorized(update.effective_user.id):
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    print(f"[msg] Received from {update.effective_user.id}: {user_text[:80]}...")

    # Let user know we're working
    waiting = await update.message.reply_text("📥 收到，正在處理...")

    try:
        if is_url(user_text):
            # Extract the actual URL (handles Telegram share format: "Title\nhttps://...")
            actual_url = extract_url(user_text)
            await _handle_url(update, context, waiting, actual_url)
        else:
            await _handle_text(update, context, waiting, user_text)
    except Exception as e:
        await waiting.edit_text(f"❌ 處理時發生錯誤：{str(e)[:200]}")
        import traceback
        traceback.print_exc()


async def _handle_url(update: Update, context, waiting, url: str):
    """Handle a shared URL."""
    await waiting.edit_text("🌐 正在抓取網頁內容...")

    # Fetch content
    result = await fetch_url_content(url)

    if not result["success"]:
        await waiting.edit_text(
            f"❌ 無法抓取網頁內容\n{result.get('error', '未知錯誤')}\n\n"
            "可能原因：\n"
            "• 網頁需要登入才能看\n"
            "• 網站有反爬機制\n"
            "• 網址無效"
        )
        return

    title = result.get("title") or result["source_domain"]
    content_text = result.get("content", "")
    summary = result.get("summary", "")
    source_domain = result.get("source_domain", "")

    if not content_text:
        await waiting.edit_text("❌ 無法取得網頁內容（可能是需要登入的頁面）")
        return

    # Generate unique ID
    article_id = generate_article_id(title, url)

    # Generate and save HTML
    await waiting.edit_text("📄 正在生成 HTML...")
    content_is_html = result.get("content_is_html", False)
    file_path = html_generator.save_html(
        article_id, title, url, source_domain, content_text, summary, content_is_html
    )

    # ── Auto-verify formatting quality ──
    quality = verify_formatting(content_text, content_is_html)
    if not quality["passed"]:
        print(f"[Quality] ⚠️ POOR FORMATTING for {article_id}:")
        print(f"[Quality]    score={quality['score']}, issues: {quality['issues']}")
        print(f"[Quality]    tags found: {quality['structural_tags']}")
    else:
        print(f"[Quality] ✅ FORMATTING OK for {article_id}: score={quality['score']}")

    # Save to database
    db.insert_article(article_id, title, url, source_domain, file_path, content_text)

    # Sync to Google Drive
    drive_result = None
    try:
        await waiting.edit_text("☁️ 正在同步到 Google Drive...")
        drive_result = gdrive_sync.sync_article(file_path, article_id, title)
        if drive_result and drive_result.get("status") == "uploaded":
            drive_file_id = drive_result.get("id", "")
            db.update_drive_file_id(article_id, drive_file_id)
    except Exception as e:
        print(f"[GDrive] Sync failed: {e}")

    # Build summary message
    char_count = len(content_text)
    summary_parts = [
        f"✅ *已儲存知識點*",
        f"",
        f"📌 *{title}*",
        f"🔗 {url}",
        f"🌐 {source_domain}",
        f"📝 {char_count:,} 字元",
    ]

    if summary and len(summary) < 200:
        summary_parts.append(f"")
        summary_parts.append(f"📋 *摘要：* {summary}")

    drive_file_id = drive_result.get("id", "") if drive_result else ""
    if drive_result and drive_result.get("status") == "uploaded":
        drive_link = drive_result.get("webViewLink", "")
        summary_parts.append(f"")
        summary_parts.append(f"☁️ Google Drive ✅")
        if drive_link:
            summary_parts.append(f"[在 Drive 中開啟]({drive_link})")
    elif not config.GDRIVE_ENABLED:
        summary_parts.append(f"")
        summary_parts.append(f"☁️ GDrive 同步未啟用")

    summary_parts.append(f"")
    summary_parts.append(f"🆔 `{article_id}`")

    await waiting.edit_text("\n".join(summary_parts), parse_mode=ParseMode.MARKDOWN)

    # ── Send a readable content preview instead of .html file ──
    try:
        if content_is_html:
            # Strip HTML tags for a readable preview
            preview = re.sub(r'<style[^>]*>.*?</style>', '', content_text, flags=re.DOTALL | re.IGNORECASE)
            preview = re.sub(r'<script[^>]*>.*?</script>', '', preview, flags=re.DOTALL | re.IGNORECASE)
            preview = re.sub(r'<[^>]+>', ' ', preview)
            preview = re.sub(r'\s+', ' ', preview).strip()
        else:
            preview = content_text

        # Truncate preview
        if len(preview) > 800:
            preview = preview[:800] + "…\n\n（完整內容請在 Google Drive 開啟）"

        await update.message.reply_text(
            f"📄 *內容預覽*\n\n{preview}",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"[Bot] Send preview error: {e}")


async def _handle_text(update: Update, context, waiting, text: str):
    """Handle shared plain text."""
    article_id = generate_article_id(text[:50])
    title = text[:80] + ("..." if len(text) > 80 else "")

    # Generate HTML
    file_path = html_generator.save_html(
        article_id, title, "", "", text
    )

    # Save to database
    db.insert_article(article_id, title, "", "", file_path, text)

    # Sync to Drive
    drive_file_id = ""
    try:
        drive_file_id = gdrive_sync.sync_article(file_path, article_id, title)
        if drive_file_id:
            db.update_drive_file_id(article_id, drive_file_id)
    except Exception:
        pass

    char_count = len(text)
    reply = (
        f"✅ *已儲存知識點*\n\n"
        f"📝 文字筆記\n"
        f"📝 {char_count:,} 字元\n"
    )
    if drive_file_id:
        reply += f"\n☁️ Google Drive ✅"

    await waiting.edit_text(reply, parse_mode=ParseMode.MARKDOWN)

    # Send a content preview
    try:
        preview = text.strip()
        if len(preview) > 800:
            preview = preview[:800] + "…\n\n（完整內容請在 Google Drive 開啟）"
        await update.message.reply_text(
            f"📄 *內容預覽*\n\n{preview}",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"[Bot] Send text preview error: {e}")
        pass


async def list_articles(update: Update, context):
    if not _is_authorized(update.effective_user.id):
        return

    rows = db.list_recent(20)
    if not rows:
        await update.message.reply_text("📭 知識庫目前是空的。")
        return

    lines = ["📚 *最近儲存的知識*\n"]
    for r in rows:
        domain = f" ({r['source_domain']})" if r['source_domain'] else ""
        lines.append(f"• `{r['id']}` — {r['title']}{domain}")
    lines.append(f"\n共 {len(rows)} 項")

    # Split if too long
    msg = "\n".join(lines)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n...（內容過長）"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def stats(update: Update, context):
    if not _is_authorized(update.effective_user.id):
        return

    s = db.get_stats()
    lines = [
        "📊 *知識庫統計*\n",
        f"📚 知識點總數：**{s['total']}**",
        f"📝 總字元數：**{s['total_chars']:,}**",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def search(update: Update, context):
    if not _is_authorized(update.effective_user.id):
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ 請輸入搜尋關鍵字\n例如：`/search OpenClaw`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    query = " ".join(args)
    results = db.search_articles(query)

    if not results:
        await update.message.reply_text(f"🔍 沒有找到與「{query}」相關的知識點。")
        return

    lines = [f"🔍 *搜尋「{query}」的結果*\n"]
    for r in results:
        domain = f" ({r['source_domain']})" if r['source_domain'] else ""
        lines.append(f"• `{r['id']}` — {r['title']}{domain}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def ask_handler(update: Update, context):
    """Handle /ask — correct and answer a technical question via Hermes API."""
    if not _is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ 請輸入你的問題\n"
            "例如：`/ask 什麼是 interface providers？`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    question = " ".join(context.args)
    waiting = await update.message.reply_text("🤔 推理中，請稍候...")

    try:
        answer = await ask_hermes(question)
        # Telegram has a 4096 char limit per message
        if len(answer) > 4000:
            parts = [answer[i:i+4000] for i in range(0, len(answer), 4000)]
            for i, part in enumerate(parts):
                prefix = f"（{i+1}/{len(parts)}）\n\n" if len(parts) > 1 else ""
                msg_text = prefix + part
                if i == 0:
                    await waiting.edit_text(msg_text, parse_mode=ParseMode.MARKDOWN)
                else:
                    await update.message.reply_text(msg_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await waiting.edit_text(answer, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await waiting.edit_text(f"❌ 處理問題時發生錯誤：{str(e)[:200]}")


# ── Main ──

def main():
    print("[init] Initializing database...")
    db.init_db()

    print(f"[init] Config:\n{dump_config()}")

    print("[init] Starting Know_Bot...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_articles))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("ask", ask_handler))

    # Text handler — catch all text messages (URLs + plain text)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("[init] Know_Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()