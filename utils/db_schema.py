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
        -- Lưu parent text bền vững để không cần re-ingest sau khi restart.
        CREATE TABLE IF NOT EXISTS parent_chunks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id      TEXT    NOT NULL,
            parent_id       TEXT    NOT NULL,   -- "{doc_name}_p{page}_parent{idx}"
            parent_text     TEXT    NOT NULL,
            file_path       TEXT    NOT NULL,
            page_num        INTEGER NOT NULL,
            doc_name        TEXT    NOT NULL,
            UNIQUE(subject_id, parent_id)       -- upsert an toàn
        );
        CREATE INDEX IF NOT EXISTS idx_parent_chunks_lookup
            ON parent_chunks(subject_id, parent_id);
        CREATE INDEX IF NOT EXISTS idx_parent_chunks_doc
            ON parent_chunks(subject_id, doc_name);

        -- Experiment Runs
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

        -- RAGAS and Retrieval Results
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

        -- Bảng 1: benchmark_runs (Ghi nhận tự động)
        CREATE TABLE IF NOT EXISTS benchmark_runs (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp                   TEXT NOT NULL,
            question_id                 INTEGER NOT NULL,
            query                       TEXT NOT NULL,
            rewritten_query             TEXT,
            chunking_strategy           TEXT NOT NULL,
            chunking_version            TEXT NOT NULL DEFAULT 'v1',
            rag_mode                    TEXT NOT NULL,
            attempts                    INTEGER NOT NULL DEFAULT 1,
            experiment_seed             INTEGER NOT NULL DEFAULT 42,
            dataset_version             TEXT NOT NULL,
            prompt_template_version     TEXT NOT NULL,
            chunk_size                  INTEGER,
            chunk_overlap               INTEGER,
            
            -- Metadata môi trường thực thi (Tái lập nghiên cứu)
            git_commit_hash             TEXT,
            machine_name                TEXT,
            gpu_name                    TEXT,
            ram_gb                      INTEGER,
            ollama_version              TEXT,
            os_version                  TEXT,
            
            -- Siêu dữ liệu mô hình và tham số cấu hình
            embedding_provider          TEXT NOT NULL,
            embedding_model             TEXT NOT NULL,
            embedding_dimension         INTEGER NOT NULL,
            generator_model             TEXT NOT NULL,
            generator_temperature       REAL NOT NULL DEFAULT 0.0,
            grader_model                TEXT NOT NULL,
            grader_temperature          REAL NOT NULL DEFAULT 0.0,
            
            -- Thống kê số lượng và độ dài ngữ cảnh
            raw_retrieved_count_l1      INTEGER NOT NULL DEFAULT 0,
            raw_retrieved_count_l2      INTEGER NOT NULL DEFAULT 0,
            filtered_chunk_count_l1     INTEGER NOT NULL DEFAULT 0,
            filtered_chunk_count_l2     INTEGER NOT NULL DEFAULT 0,
            context_chunk_count         INTEGER NOT NULL,
            context_char_count          INTEGER NOT NULL,
            
            -- Cấu trúc JSON chi tiết phục vụ đo Hit@k, MRR
            retrieved_chunks_json_l1    TEXT NOT NULL DEFAULT '[]',
            retrieved_chunks_json_l2    TEXT NOT NULL DEFAULT '[]',
            final_chunks_json           TEXT NOT NULL DEFAULT '[]',
            
            -- Các trường lưu Hit@k và Recall@k trực tiếp
            hit_at_1_l1                 INTEGER NOT NULL DEFAULT 0,
            hit_at_3_l1                 INTEGER NOT NULL DEFAULT 0,
            hit_at_5_l1                 INTEGER NOT NULL DEFAULT 0,
            recall_at_1_l1              REAL NOT NULL DEFAULT 0.0,
            recall_at_3_l1              REAL NOT NULL DEFAULT 0.0,
            recall_at_5_l1              REAL NOT NULL DEFAULT 0.0,
            
            hit_at_1_l2                 INTEGER NOT NULL DEFAULT 0,
            hit_at_3_l2                 INTEGER NOT NULL DEFAULT 0,
            hit_at_5_l2                 INTEGER NOT NULL DEFAULT 0,
            recall_at_1_l2              REAL NOT NULL DEFAULT 0.0,
            recall_at_3_l2              REAL NOT NULL DEFAULT 0.0,
            recall_at_5_l2              REAL NOT NULL DEFAULT 0.0,
            
            first_relevant_rank_l1      INTEGER NOT NULL DEFAULT 999,
            first_relevant_rank_l2      INTEGER NOT NULL DEFAULT 999,
            
            -- Điểm tương đồng tốt nhất phục vụ phân tích điều kiện
            best_similarity_l1          REAL NOT NULL DEFAULT 0.0,
            best_similarity_l2          REAL NOT NULL DEFAULT 0.0,
            
            -- Kết quả chấm điểm Grader (Thang điểm 0-5)
            grader_score_l1             INTEGER NOT NULL DEFAULT 0,
            grader_score_l2             INTEGER NOT NULL DEFAULT 0,
            retrieval_success_grader_l1 INTEGER NOT NULL DEFAULT 0,
            retrieval_success_grader_l2 INTEGER NOT NULL DEFAULT 0,
            
            rewrite_activated           INTEGER NOT NULL DEFAULT 0,
            final_answer                TEXT NOT NULL,
            
            -- Chỉ số Tokens từ Ollama
            prompt_tokens               INTEGER NOT NULL,
            completion_tokens           INTEGER NOT NULL,
            total_tokens                INTEGER NOT NULL,
            
            -- Thời gian chạy (ms)
            retrieval_time_ms           REAL NOT NULL,
            grading_time_ms             REAL NOT NULL,
            rewrite_time_ms             REAL NOT NULL,
            generation_time_ms          REAL NOT NULL,
            total_time_ms               REAL NOT NULL,
            final_answer_length         INTEGER NOT NULL
        );
        -- Bảng 2: evaluation_results (Human Evaluation Layer)
        -- Chỉ ghi kết quả chấm điểm thủ công, tách biệt khỏi runtime.
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

    # ── Idempotent Migration for experiment_runs ──────────────────────────────
    cur.execute("PRAGMA table_info(experiment_runs)")
    existing_columns = [row[1] for row in cur.fetchall()]
    
    new_cols = {
        "judge_provider": "TEXT",
        "judge_model": "TEXT",
        "judge_temperature": "REAL",
        "judge_context_window": "INTEGER",
        "ragas_version": "TEXT",
        "embedding_model": "TEXT"
    }
    
    for col_name, col_type in new_cols.items():
        if col_name not in existing_columns:
            cur.execute(f"ALTER TABLE experiment_runs ADD COLUMN {col_name} {col_type}")
            print(f"[DB Migration] Added column '{col_name}' to 'experiment_runs'")

    # ── Idempotent Migration for benchmark_runs ──────────────────────────────
    cur.execute("PRAGMA table_info(benchmark_runs)")
    existing_benchmark_columns = [row[1] for row in cur.fetchall()]
    if existing_benchmark_columns:
        expected_benchmark_cols = {
            "timestamp": "TEXT NOT NULL",
            "question_id": "INTEGER NOT NULL",
            "query": "TEXT NOT NULL",
            "rewritten_query": "TEXT",
            "chunking_strategy": "TEXT NOT NULL",
            "chunking_version": "TEXT NOT NULL DEFAULT 'v1'",
            "rag_mode": "TEXT NOT NULL",
            "attempts": "INTEGER NOT NULL DEFAULT 1",
            "experiment_seed": "INTEGER NOT NULL DEFAULT 42",
            "dataset_version": "TEXT NOT NULL",
            "prompt_template_version": "TEXT NOT NULL",
            "chunk_size": "INTEGER",
            "chunk_overlap": "INTEGER",
            "git_commit_hash": "TEXT",
            "machine_name": "TEXT",
            "gpu_name": "TEXT",
            "ram_gb": "INTEGER",
            "ollama_version": "TEXT",
            "os_version": "TEXT",
            "embedding_provider": "TEXT NOT NULL",
            "embedding_model": "TEXT NOT NULL",
            "embedding_dimension": "INTEGER NOT NULL",
            "generator_model": "TEXT NOT NULL",
            "generator_temperature": "REAL NOT NULL DEFAULT 0.0",
            "grader_model": "TEXT NOT NULL",
            "grader_temperature": "REAL NOT NULL DEFAULT 0.0",
            "raw_retrieved_count_l1": "INTEGER NOT NULL DEFAULT 0",
            "raw_retrieved_count_l2": "INTEGER NOT NULL DEFAULT 0",
            "filtered_chunk_count_l1": "INTEGER NOT NULL DEFAULT 0",
            "filtered_chunk_count_l2": "INTEGER NOT NULL DEFAULT 0",
            "context_chunk_count": "INTEGER NOT NULL",
            "context_char_count": "INTEGER NOT NULL",
            "retrieved_chunks_json_l1": "TEXT NOT NULL DEFAULT '[]'",
            "retrieved_chunks_json_l2": "TEXT NOT NULL DEFAULT '[]'",
            "final_chunks_json": "TEXT NOT NULL DEFAULT '[]'",
            "hit_at_1_l1": "INTEGER NOT NULL DEFAULT 0",
            "hit_at_3_l1": "INTEGER NOT NULL DEFAULT 0",
            "hit_at_5_l1": "INTEGER NOT NULL DEFAULT 0",
            "recall_at_1_l1": "REAL NOT NULL DEFAULT 0.0",
            "recall_at_3_l1": "REAL NOT NULL DEFAULT 0.0",
            "recall_at_5_l1": "REAL NOT NULL DEFAULT 0.0",
            "hit_at_1_l2": "INTEGER NOT NULL DEFAULT 0",
            "hit_at_3_l2": "INTEGER NOT NULL DEFAULT 0",
            "hit_at_5_l2": "INTEGER NOT NULL DEFAULT 0",
            "recall_at_1_l2": "REAL NOT NULL DEFAULT 0.0",
            "recall_at_3_l2": "REAL NOT NULL DEFAULT 0.0",
            "recall_at_5_l2": "REAL NOT NULL DEFAULT 0.0",
            "first_relevant_rank_l1": "INTEGER NOT NULL DEFAULT 999",
            "first_relevant_rank_l2": "INTEGER NOT NULL DEFAULT 999",
            "best_similarity_l1": "REAL NOT NULL DEFAULT 0.0",
            "best_similarity_l2": "REAL NOT NULL DEFAULT 0.0",
            "grader_score_l1": "INTEGER NOT NULL DEFAULT 0",
            "grader_score_l2": "INTEGER NOT NULL DEFAULT 0",
            "retrieval_success_grader_l1": "INTEGER NOT NULL DEFAULT 0",
            "retrieval_success_grader_l2": "INTEGER NOT NULL DEFAULT 0",
            "rewrite_activated": "INTEGER NOT NULL DEFAULT 0",
            "final_answer": "TEXT NOT NULL",
            "prompt_tokens": "INTEGER NOT NULL",
            "completion_tokens": "INTEGER NOT NULL",
            "total_tokens": "INTEGER NOT NULL",
            "retrieval_time_ms": "REAL NOT NULL",
            "grading_time_ms": "REAL NOT NULL",
            "rewrite_time_ms": "REAL NOT NULL",
            "generation_time_ms": "REAL NOT NULL",
            "total_time_ms": "REAL NOT NULL",
            "final_answer_length": "INTEGER NOT NULL"
        }
        for col_name, col_def in expected_benchmark_cols.items():
            if col_name not in existing_benchmark_columns:
                alter_def = col_def
                if "NOT NULL" in alter_def and "DEFAULT" not in alter_def:
                    alter_def = alter_def.replace("NOT NULL", "")
                cur.execute(f"ALTER TABLE benchmark_runs ADD COLUMN {col_name} {alter_def}")
                print(f"[DB Migration] Added column '{col_name}' to 'benchmark_runs'")

    # ── Idempotent Migration for evaluation_results ──────────────────────────
    cur.execute("PRAGMA table_info(evaluation_results)")
    existing_eval_columns = [row[1] for row in cur.fetchall()]
    expected_eval_cols = {
        "evaluated_at": "TEXT",
        "notes":        "TEXT",
    }
    for col_name, col_type in expected_eval_cols.items():
        if col_name not in existing_eval_columns:
            cur.execute(f"ALTER TABLE evaluation_results ADD COLUMN {col_name} {col_type}")
            print(f"[DB Migration] Added column '{col_name}' to 'evaluation_results'")

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
