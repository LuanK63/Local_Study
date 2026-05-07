"""
utils/db_schema.py
Initialize and migrate SQLite database.
All tables include subject_id to isolate data per subject.
"""
import sqlite3
import os
from utils.config import get_config

def get_db_path() -> str:
    cfg = get_config()
    return cfg["database"]["path"]

def init_db():
    """Create all tables if they don't exist."""
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript("""
        -- Conversation history (Module 1, 3, 4)
        CREATE TABLE IF NOT EXISTS conversations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            subject_id      TEXT    NOT NULL,
            module          TEXT    NOT NULL,
            query           TEXT    NOT NULL,
            answer          TEXT,
            sources         TEXT    -- JSON: [{file, page, score}]
        );

        -- Quiz sessions (Module 6)
        CREATE TABLE IF NOT EXISTS quiz_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            subject_id      TEXT    NOT NULL,
            topic_id        TEXT,
            question        TEXT    NOT NULL,
            options         TEXT,   -- JSON: ["opt_a", "opt_b", "opt_c", "opt_d"]
            correct_answer  TEXT    NOT NULL,
            user_answer     TEXT,
            is_correct      INTEGER,
            explanation     TEXT
        );

        -- Practice sessions (Module 7)
        CREATE TABLE IF NOT EXISTS practice_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            subject_id      TEXT    NOT NULL,
            topic_id        TEXT,
            type            TEXT    NOT NULL, -- 'text' | 'code'
            question        TEXT    NOT NULL,
            user_answer     TEXT,
            score           REAL,
            feedback        TEXT
        );

        -- Flashcards (Module 9)
        CREATE TABLE IF NOT EXISTS flashcards (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id      TEXT    NOT NULL,
            front           TEXT    NOT NULL,
            back            TEXT    NOT NULL,
            source          TEXT,   -- file:page
            created_at      TEXT    NOT NULL,
            last_reviewed   TEXT,
            ease_factor     REAL    DEFAULT 2.5
        );

        -- Code sandbox runs (Module 4b)
        CREATE TABLE IF NOT EXISTS code_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            subject_id      TEXT    NOT NULL,
            lang            TEXT    NOT NULL, -- 'c' | 'cpp' | 'python'
            code            TEXT    NOT NULL,
            stdin           TEXT,
            stdout          TEXT,
            stderr          TEXT,
            elapsed_ms      REAL,
            passed_cases    INTEGER DEFAULT 0,
            total_cases     INTEGER DEFAULT 0
        );
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {db_path}")


def get_connection() -> sqlite3.Connection:
    """Return a connection to the database (with row_factory)."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


if __name__ == "__main__":
    init_db()
