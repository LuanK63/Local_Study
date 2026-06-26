"""
research/database/init_benchmark_db.py
======================================
Khởi tạo schema cho database benchmark độc lập (benchmark_logs.db).
"""
import sqlite3
import os

def get_benchmark_db_path() -> str:
    """Trả về đường dẫn tuyệt đối đến file benchmark_logs.db."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(base_dir, "data", "benchmark_logs.db")
    return db_path

def init_benchmark_db():
    """Tạo các bảng cho benchmark."""
    db_path = get_benchmark_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_name TEXT NOT NULL,
            chunking_config TEXT NOT NULL,  -- JSON string
            dataset_version TEXT NOT NULL,
            retrieval_version TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS benchmark_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            precision_at_5 REAL,
            recall_at_5 REAL,
            f1_at_5 REAL,
            hit_rate_at_5 REAL,
            mrr REAL,
            retrieval_latency REAL,
            FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS question_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            question_id TEXT NOT NULL,
            hit_rate REAL,
            mrr REAL,
            retrieval_latency REAL,
            FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS chunk_statistics (
            experiment_id INTEGER PRIMARY KEY,
            total_chunks INTEGER,
            avg_chunk_size REAL,
            median_chunk_size REAL,
            min_chunk_size INTEGER,
            max_chunk_size INTEGER,
            ingestion_time_seconds REAL,
            FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE
        );
    """)
    
    conn.commit()
    conn.close()
    print(f"[Benchmark DB] Initialized at {db_path}")

def get_benchmark_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_benchmark_db_path())
    conn.row_factory = sqlite3.Row
    return conn

if __name__ == "__main__":
    init_benchmark_db()
