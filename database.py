import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'blog_marketing.db')


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                topic        TEXT    NOT NULL,
                blog_path    TEXT,
                linkedin_text TEXT,
                hashtags     TEXT,
                status       TEXT    NOT NULL DEFAULT 'draft',
                publish_date TEXT,
                created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()


def insert_post(topic: str, blog_path: str, linkedin_text: str,
                hashtags: str, status: str = 'draft', publish_date: str = None) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            '''INSERT INTO posts (topic, blog_path, linkedin_text, hashtags, status, publish_date)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (topic, blog_path, linkedin_text, hashtags, status, publish_date)
        )
        conn.commit()
        return cursor.lastrowid


def update_post_status(post_id: int, status: str):
    with get_connection() as conn:
        conn.execute('UPDATE posts SET status = ? WHERE id = ?', (status, post_id))
        conn.commit()


def get_post_by_id(post_id: int):
    with get_connection() as conn:
        return conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()


def get_scheduled_posts() -> list:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM posts WHERE status = 'scheduled' ORDER BY publish_date"
        ).fetchall()


def get_all_posts() -> list:
    with get_connection() as conn:
        return conn.execute(
            'SELECT * FROM posts ORDER BY created_at DESC'
        ).fetchall()
