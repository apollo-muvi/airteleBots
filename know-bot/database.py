"""
Know_Bot Database — SQLite index for saved knowledge.
"""
import sqlite3
import os
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source_url TEXT,
            source_domain TEXT,
            date TEXT NOT NULL,
            summary TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            file_path TEXT NOT NULL,
            drive_file_id TEXT DEFAULT '',
            char_count INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id TEXT NOT NULL,
            tag TEXT NOT NULL,
            UNIQUE(article_id, tag),
            FOREIGN KEY (article_id) REFERENCES articles(id)
        );
    """)
    conn.commit()
    conn.close()


def insert_article(article_id, title, source_url, source_domain, file_path, content):
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO articles
           (id, title, source_url, source_domain, date, file_path, char_count, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (article_id, title, source_url, source_domain,
         datetime.now().strftime("%Y-%m-%d %H:%M"),
         file_path, len(content), datetime.now().timestamp())
    )
    conn.commit()
    conn.close()


def update_drive_file_id(article_id, drive_file_id):
    conn = get_conn()
    conn.execute("UPDATE articles SET drive_file_id = ? WHERE id = ?",
                 (drive_file_id, article_id))
    conn.commit()
    conn.close()


def update_tags(article_id, tag_str):
    conn = get_conn()
    conn.execute("UPDATE articles SET tags = ? WHERE id = ?",
                 (tag_str, article_id))
    conn.commit()
    conn.close()


def get_article(article_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_recent(limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, source_domain, date, char_count FROM articles ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_articles(query):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, source_domain, date FROM articles WHERE title LIKE ? OR tags LIKE ? ORDER BY created_at DESC LIMIT 20",
        (f"%{query}%", f"%{query}%")
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    total_chars = conn.execute("SELECT COALESCE(SUM(char_count), 0) FROM articles").fetchone()[0]
    conn.close()
    return {"total": total, "total_chars": total_chars}