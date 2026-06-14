"""Database module — SQLite CRUD for vocabulary storage.

Tables:
  words (id, word, created_at)
  definitions (id, word_id, part_of_speech, uk_phonetic, us_phonetic,
               definition_en, definition_zh, example_en, example_zh)
"""

import sqlite3
import time
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            part_of_speech TEXT,
            uk_phonetic TEXT,
            us_phonetic TEXT,
            definition_en TEXT,
            definition_zh TEXT,
            example_en TEXT,
            example_zh TEXT,
            FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_words_word ON words(word);
        CREATE INDEX IF NOT EXISTS idx_definitions_word_id ON definitions(word_id);
    """)
    conn.commit()
    conn.close()


# ── Write ──

def save_word(word: str, results: list[dict]) -> bool:
    """Save a word and its definitions. Returns True if new, False if existed."""
    conn = get_conn()
    cur = conn.cursor()
    word_lower = word.strip().lower()

    cur.execute("SELECT id FROM words WHERE word = ?", (word_lower,))
    existing = cur.fetchone()

    if existing:
        word_id = existing["id"]
        is_new = False
        # Still update definitions (in case the LLM returns richer data)
        cur.execute("DELETE FROM definitions WHERE word_id = ?", (word_id,))
    else:
        cur.execute(
            "INSERT INTO words (word, created_at) VALUES (?, ?)",
            (word_lower, int(time.time())),
        )
        word_id = cur.lastrowid
        is_new = True

    for res in results:
        cur.execute("""
            INSERT INTO definitions
                (word_id, part_of_speech, uk_phonetic, us_phonetic,
                 definition_en, definition_zh, example_en, example_zh)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            word_id,
            res.get("part_of_speech"),
            res.get("uk_phonetic"),
            res.get("us_phonetic"),
            res.get("definition_en"),
            res.get("definition_zh"),
            res.get("example_en"),
            res.get("example_zh"),
        ))

    conn.commit()
    conn.close()
    return is_new


# ── Read ──

def lookup_word(word: str) -> dict | None:
    """Look up a word in the local DB. Returns dict or None."""
    conn = get_conn()
    cur = conn.cursor()
    word_lower = word.strip().lower()

    cur.execute("SELECT id, word, created_at FROM words WHERE word = ?", (word_lower,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    word_id = row["id"]
    cur.execute("""
        SELECT part_of_speech, uk_phonetic, us_phonetic,
               definition_en, definition_zh, example_en, example_zh
        FROM definitions WHERE word_id = ?
    """, (word_id,))
    defs = [dict(r) for r in cur.fetchall()]
    conn.close()

    return {
        "word": row["word"],
        "results": defs,
        "cached": True,
    }


def list_recent_words(limit: int = 10) -> list[dict]:
    """List the most recently queried words."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT w.word, w.created_at, COUNT(d.id) as def_count
        FROM words w
        LEFT JOIN definitions d ON d.word_id = w.id
        GROUP BY w.id
        ORDER BY w.created_at DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_stats() -> dict:
    """Get vocabulary statistics."""
    conn = get_conn()
    cur = conn.cursor()
    total_words = cur.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    total_defs = cur.execute("SELECT COUNT(*) FROM definitions").fetchone()[0]
    # Most common part of speech
    cur.execute("""
        SELECT part_of_speech, COUNT(*) as c
        FROM definitions
        WHERE part_of_speech IS NOT NULL AND part_of_speech != ''
        GROUP BY part_of_speech
        ORDER BY c DESC
        LIMIT 1
    """)
    top_pos = cur.fetchone()
    conn.close()
    return {
        "total_words": total_words,
        "total_definitions": total_defs,
        "top_part_of_speech": dict(top_pos) if top_pos else None,
    }


def export_all() -> list[dict]:
    """Export all words with definitions for CSV/Anki export."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT w.word, d.part_of_speech, d.definition_en, d.definition_zh,
               d.example_en, d.example_zh
        FROM words w
        JOIN definitions d ON d.word_id = w.id
        ORDER BY w.word
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows