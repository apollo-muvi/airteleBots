"""Telegram Bot handlers for the English Dictionary Bot."""

import csv
import io
import os
import re
import tempfile
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import config
import database as db
import dictionary as dict_lib
import tts_handler as tts


# ── Helpers ──

def _is_authorized(user_id: int) -> bool:
    if config.ALLOW_ALL:
        return True
    return str(user_id) in config.ALLOWED_USERS


# ── Formatting ──

def _format_word_response(data: dict) -> str:
    """Format dictionary data as a nice Telegram message."""
    word = data.get("word", "").upper()
    lines = [f"📖 *{word}*\n"]

    for i, item in enumerate(data.get("results", [])):
        pos = item.get("part_of_speech", "")
        uk = item.get("uk_phonetic", "")
        us = item.get("us_phonetic", "")

        # Phonetics line
        phonetics_parts = []
        if uk:
            phonetics_parts.append(f"UK: `{uk}`")
        if us:
            phonetics_parts.append(f"US: `{us}`")
        phonetics_str = " | ".join(phonetics_parts)

        header = f"▸ *[{pos}]*" if pos else "▸"
        if phonetics_str:
            header += f"  {phonetics_str}"
        lines.append(header)

        # Definitions
        def_en = item.get("definition_en", "")
        def_zh = item.get("definition_zh", "")
        if def_en:
            lines.append(f"💡 *En:* {def_en}")
        if def_zh:
            lines.append(f"    *繁中:* {def_zh}")

        # Example
        ex_en = item.get("example_en", "")
        ex_zh = item.get("example_zh", "")
        if ex_en:
            lines.append(f"📝 *Ex:* {ex_en}")
        if ex_zh:
            lines.append(f"    *翻譯:* {ex_zh}")

        if i < len(data.get("results", [])) - 1:
            lines.append("")

    # Pronunciation buttons footer
    word_clean = data.get("word", "").lower()
    lines.append("")
    lines.append("🔊 發音：")

    return "\n".join(lines)


async def _send_pronunciation_buttons(update: Update, word: str):
    """Send pronunciation audio buttons."""
    keyboard = [
        [
            InlineKeyboardButton("🔊 英式 UK", callback_data=f"tts_uk_{word}"),
            InlineKeyboardButton("🔊 美式 US", callback_data=f"tts_us_{word}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("點擊收聽發音：", reply_markup=reply_markup)


# ── Handlers ──

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message."""
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ 你沒有使用這個 bot 的權限。")
        return

    welcome = (
        "📖 *English Dictionary Bot*\n\n"
        "傳送任何英文單字，我會幫你查詢劍橋字典風格的解釋！\n\n"
        "🔹 *指令：*\n"
        "  `/list` — 最近查過的單字\n"
        "  `/export` — 匯出單字庫 (CSV)\n"
        "  `/export anki` — 匯出 Anki 相容格式\n"
        "  `/stats` — 查詢統計\n\n"
        "🔹 *範例：*\n"
        "  傳送 `apple` → 取得完整解釋 + 發音"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)


async def handle_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a text message — treat it as a word to look up."""
    if not _is_authorized(update.effective_user.id):
        return

    user_word = update.message.text.strip()

    # Basic validation: must be a single word or short phrase
    words = user_word.split()
    if len(words) > 4:
        await update.message.reply_text(
            "⚠️ 請輸入單個英文單字或短語（例如：`apple` 或 `look up`）。"
        )
        return

    # Only allow letters, hyphens, spaces (for phrasal verbs)
    if not re.match(r'^[a-zA-Z\-\s]+$', user_word):
        await update.message.reply_text("⚠️ 請輸入英文單字。")
        return

    word_lower = user_word.strip().lower()

    # Step 1: Check local cache
    cached = db.lookup_word(word_lower)
    if cached:
        reply = _format_word_response(cached)
        reply += "\n\n_⚡ 來自快取_"
        msg = await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
        await _send_pronunciation_buttons(update, word_lower)
        return

    # Step 2: Call Hermes API
    waiting = await update.message.reply_text(f"🔍 正在查詢 '{user_word}'，請稍候...")

    dict_data = dict_lib.query(word_lower)
    if not dict_data or "results" not in dict_data or not dict_data["results"]:
        await waiting.edit_text(
            f"❌ 查詢失敗，請稍後再試。\n\n"
            f"可能原因：\n"
            f"• Hermes API Server 未啟動\n"
            f"• 單字拼寫有誤\n"
            f"• LLM 回傳格式異常\n\n"
            f"請檢查後台日誌。"
        )
        return

    # Step 3: Save to database
    db.save_word(word_lower, dict_data["results"])

    # Step 4: Format and send
    reply = _format_word_response(dict_data)
    await waiting.edit_text(reply, parse_mode=ParseMode.MARKDOWN)

    # Step 5: Send pronunciation buttons
    await _send_pronunciation_buttons(update, word_lower)


async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recently queried words."""
    if not _is_authorized(update.effective_user.id):
        return

    rows = db.list_recent_words(limit=15)
    if not rows:
        await update.message.reply_text("📭 還沒有查過任何單字。")
        return

    lines = ["📋 *最近查過的單字*\n"]
    for r in rows:
        ts = datetime.fromtimestamp(r["created_at"]).strftime("%m/%d %H:%M")
        lines.append(f"• `{r['word']}` — {r['def_count']} 個解釋 ({ts})")

    lines.append(f"\n共 {len(rows)} 個單字")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show vocabulary statistics."""
    if not _is_authorized(update.effective_user.id):
        return

    s = db.get_stats()
    lines = [
        "📊 *單字庫統計*\n",
        f"📚 單字數量：**{s['total_words']}**",
        f"📝 解釋數量：**{s['total_definitions']}**",
    ]
    if s["top_part_of_speech"]:
        lines.append(
            f"🏷️ 最常見詞性：**{s['top_part_of_speech']['part_of_speech']}** "
            f"({s['top_part_of_speech']['c']} 次)"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export vocabulary as CSV or Anki format."""
    if not _is_authorized(update.effective_user.id):
        return

    rows = db.export_all()
    if not rows:
        await update.message.reply_text("📭 還沒有任何單字可以匯出。")
        return

    # Check if user wants Anki format
    args = context.args
    is_anki = args and args[0].lower() == "anki"

    if is_anki:
        # Anki format: word, definition (tab-separated)
        output = io.StringIO()
        seen = set()
        for r in rows:
            w = r["word"]
            if w not in seen:
                seen.add(w)
                def_text = "; ".join(
                    f"[{r.get('part_of_speech','')}] {r.get('definition_en','')} — {r.get('definition_zh','')}"
                    for r in rows if r["word"] == w
                )
                output.write(f"{w}\t{def_text}\n")

        csv_content = output.getvalue()
        output.close()
        fname = "vocab_anki.txt"
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["word", "part_of_speech", "definition_en", "definition_zh", "example_en", "example_zh"])
        for r in rows:
            writer.writerow([
                r["word"], r["part_of_speech"],
                r["definition_en"], r["definition_zh"],
                r["example_en"], r["example_zh"],
            ])
        csv_content = output.getvalue()
        output.close()
        fname = "vocab_export.csv"

    # Send as file
    with tempfile.NamedTemporaryFile(mode="w", suffix=f"_{fname}", delete=False) as f:
        f.write(csv_content)
        tmp_path = f.name

    with open(tmp_path, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=fname,
            caption=f"✅ 匯出完成！共 {len(rows)} 筆資料。"
        )

    os.unlink(tmp_path)


# ── Callback for pronunciation buttons ──

async def pronunciation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks for pronunciation."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("tts_"):
        return

    _, accent, word = data.split("_", 2)

    audio_files = tts.generate_pronunciation(word)
    filepath = audio_files.get(accent)

    if not filepath or not os.path.exists(filepath):
        await query.edit_message_text(
            f"❌ 無法生成 {accent.upper()} 發音。請稍後再試。"
        )
        return

    label = "英式 🇬🇧" if accent == "uk" else "美式 🇺🇸"
    with open(filepath, "rb") as f:
        await query.message.reply_audio(
            audio=f,
            title=f"{word} ({label})",
            performer="Google TTS",
        )