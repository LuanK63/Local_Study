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

        -- Parent chunks store (Parent-Child Chunking — RAG)
        CREATE TABLE IF NOT EXISTS parent_chunks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id      TEXT    NOT NULL,
            parent_id       TEXT    NOT NULL,   -- "{doc_name}_p{page}_parent{idx}"
            parent_text     TEXT    NOT NULL,
            file_path       TEXT    NOT NULL,
            page_num        INTEGER NOT NULL,
            doc_name        TEXT    NOT NULL,
            UNIQUE(subject_id, parent_id)
        );
        CREATE INDEX IF NOT EXISTS idx_parent_chunks_lookup
            ON parent_chunks(subject_id, parent_id);
        CREATE INDEX IF NOT EXISTS idx_parent_chunks_doc
            ON parent_chunks(subject_id, doc_name);

        -- Experiment Runs (Old schema, kept for backward compatibility)
        CREATE TABLE IF NOT EXISTS experiment_runs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp           TEXT    NOT NULL,
            subject_id          TEXT    NOT NULL,
            chunking_strategy   TEXT    NOT NULL,
            chunk_size          INTEGER,
            chunk_overlap       INTEGER,
            num_chunks          INTEGER,
            avg_chunk_len       REAL,
            median_chunk_len    REAL,
            total_tokens        INTEGER,
            indexing_time_s     REAL,
            avg_retrieval_time_s REAL,
            avg_generation_time_s REAL,
            avg_total_time_s    REAL
        );

        -- RAGAS and Retrieval Results (Old schema)
        CREATE TABLE IF NOT EXISTS ragas_results (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id              INTEGER,
            timestamp           TEXT    NOT NULL,
            subject_id          TEXT    NOT NULL,
            question            TEXT    NOT NULL,
            answer              TEXT,
            faithfulness        REAL,
            answer_relevancy    REAL,
            context_recall      REAL,
            context_precision   REAL,
            recall_at_5         REAL,
            recall_at_10        REAL,
            precision_at_5      REAL,
            precision_at_10     REAL,
            retrieval_time_s    REAL,
            generation_time_s   REAL,
            total_time_s        REAL,
            FOREIGN KEY(run_id) REFERENCES experiment_runs(id) ON DELETE CASCADE
        );

        -- =====================================================================
        -- NEW BENCHMARK SCHEMA (Phase 4)
        -- =====================================================================
        
        -- Table: benchmark_runs (Lưu thông tin metadata của 1 lần chạy config)
        CREATE TABLE IF NOT EXISTS benchmark_runs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp           TEXT NOT NULL,
            config_json         TEXT NOT NULL,
            dataset_name        TEXT NOT NULL,
            dataset_version     TEXT NOT NULL,
            dataset_path        TEXT NOT NULL,
            question_count      INTEGER NOT NULL,
            chunking_strategy   TEXT NOT NULL,
            chunk_size          INTEGER NOT NULL,
            index_version       TEXT NOT NULL,
            retrieval_mode      TEXT NOT NULL,
            embedding_model     TEXT NOT NULL,
            reranker_model      TEXT NOT NULL,
            latency_avg         REAL
        );

        -- Table: benchmark_scores (Lưu kết quả chi tiết cho TỪNG CÂU HỎI)
        CREATE TABLE IF NOT EXISTS benchmark_scores (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id              INTEGER NOT NULL,
            question_id         TEXT NOT NULL,
            faithfulness        REAL,
            answer_relevancy    REAL,
            context_precision   REAL,
            context_recall      REAL,
            total_latency_ms    REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES benchmark_runs(id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_benchmark_scores_unique 
            ON benchmark_scores(run_id, question_id);

        -- Table: evaluation_results (Human Evaluation Layer)
        CREATE TABLE IF NOT EXISTS evaluation_results (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id                  INTEGER NOT NULL,
            evaluator               TEXT DEFAULT 'student',
            answer_accuracy         INTEGER NOT NULL,
            citation_accuracy       REAL NOT NULL,
            notes                   TEXT,
            evaluated_at            TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES benchmark_runs(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_eval_results_run_id
            ON evaluation_results(run_id);
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
