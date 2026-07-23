import sqlite3
import uuid
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            title TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            scanned_at TEXT,
            is_expired INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            page_order INTEGER NOT NULL,
            text_content TEXT DEFAULT '',
            background_type TEXT DEFAULT 'color',
            background_value TEXT DEFAULT '#ffffff',
            font_color TEXT DEFAULT '#000000',
            font_family TEXT DEFAULT 'sans-serif',
            font_size INTEGER DEFAULT 16
        );
    """)
    conn.commit()
    conn.close()


def create_project(pages_data, title=""):
    project_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO projects (id, title, created_at) VALUES (?, ?, ?)",
        (project_id, title, now),
    )
    for i, page in enumerate(pages_data):
        conn.execute(
            "INSERT INTO pages (project_id, page_order, text_content, background_type, background_value, font_color, font_family, font_size) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, i, page.get("text", ""), page.get("bg_type", "color"), page.get("bg_value", "#ffffff"), page.get("font_color", "#000000"), page.get("font_family", "sans-serif"), page.get("font_size", 16)),
        )
    conn.commit()
    conn.close()
    return project_id


def get_project(project_id):
    conn = get_conn()
    proj = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if proj is None:
        conn.close()
        return None
    pages = conn.execute(
        "SELECT * FROM pages WHERE project_id = ? ORDER BY page_order", (project_id,)
    ).fetchall()
    conn.close()
    return {
        "id": proj["id"],
        "title": proj["title"],
        "created_at": proj["created_at"],
        "scanned_at": proj["scanned_at"],
        "is_expired": bool(proj["is_expired"]),
        "pages": [dict(p) for p in pages],
    }


def mark_scanned(project_id):
    conn = get_conn()
    proj = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if proj is None:
        conn.close()
        return False
    if proj["is_expired"] or proj["scanned_at"] is not None:
        conn.execute("UPDATE projects SET is_expired = 1 WHERE id = ?", (project_id,))
        conn.commit()
        conn.close()
        return False  # already scanned or expired
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE projects SET scanned_at = ?, is_expired = 1 WHERE id = ?",
        (now, project_id),
    )
    conn.commit()
    conn.close()
    return True  # first scan


init_db()
