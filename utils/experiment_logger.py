import os
import sqlite3
import csv
from datetime import datetime
from utils.config import get_config

def get_db_path():
    return get_config()["database"]["path"]

def get_csv_path():
    csv_dir = "data/experiments"
    os.makedirs(csv_dir, exist_ok=True)
    return os.path.join(csv_dir, "experiment_log.csv")

def median(lst):
    n = len(lst)
    if n == 0:
        return 0
    s = sorted(lst)
    return (s[n//2] + s[~(n//2)]) / 2.0

def log_ingestion(
    subject_id: str,
    strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    num_chunks: int,
    chunk_lengths: list[int],
    total_tokens: int,
    indexing_time_s: float
) -> int:
    """
    Log document ingestion metadata to experiment_runs.
    Returns the generated run_id.
    """
    import ragas
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    avg_chunk_len = sum(chunk_lengths) / len(chunk_lengths) if chunk_lengths else 0
    med_chunk_len = median(chunk_lengths)
    timestamp = datetime.now().isoformat()

    # Load judge and embedding config dynamically
    cfg = get_config()
    judge_cfg = cfg.get("judge_model", {})
    judge_provider = judge_cfg.get("provider", "ollama")
    judge_model = judge_cfg.get("model_name", "qwen2.5:14b")
    judge_temp = judge_cfg.get("temperature", 0)
    judge_ctx = judge_cfg.get("num_ctx", 4096)
    ragas_ver = ragas.__version__
    emb_model = cfg.get("embedding", {}).get("model", "nomic-embed-text")

    cur.execute(
        """
        INSERT INTO experiment_runs (
            timestamp, subject_id, chunking_strategy, chunk_size, chunk_overlap,
            num_chunks, avg_chunk_len, median_chunk_len, total_tokens, indexing_time_s,
            judge_provider, judge_model, judge_temperature, judge_context_window,
            ragas_version, embedding_model
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (timestamp, subject_id, strategy, chunk_size, chunk_overlap,
         num_chunks, avg_chunk_len, med_chunk_len, total_tokens, indexing_time_s,
         judge_provider, judge_model, judge_temp, judge_ctx, ragas_ver, emb_model)
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()

    print(f"[ExperimentLogger] Logged Ingestion Run {run_id} for {strategy}")
    return run_id

def log_query_result(
    run_id: int,
    subject_id: str,
    question: str,
    answer: str,
    faithfulness: float,
    answer_relevancy: float,
    context_recall: float,
    context_precision: float,
    recall_at_5: float,
    recall_at_10: float,
    precision_at_5: float,
    precision_at_10: float,
    retrieval_time_s: float,
    generation_time_s: float,
    total_time_s: float
):
    """
    Log individual query evaluation and timing results to ragas_results.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    timestamp = datetime.now().isoformat()

    cur.execute(
        """
        INSERT INTO ragas_results (
            run_id, timestamp, subject_id, question, answer,
            faithfulness, answer_relevancy, context_recall, context_precision,
            recall_at_5, recall_at_10, precision_at_5, precision_at_10,
            retrieval_time_s, generation_time_s, total_time_s
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, timestamp, subject_id, question, answer,
         faithfulness, answer_relevancy, context_recall, context_precision,
         recall_at_5, recall_at_10, precision_at_5, precision_at_10,
         retrieval_time_s, generation_time_s, total_time_s)
    )
    conn.commit()
    conn.close()

def update_run_averages(run_id: int):
    """
    Calculate average retrieval, generation, and total times for a run
    and update them in the experiment_runs table.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT AVG(retrieval_time_s), AVG(generation_time_s), AVG(total_time_s)
        FROM ragas_results
        WHERE run_id = ?
        """,
        (run_id,)
    )
    avg_ret, avg_gen, avg_tot = cur.fetchone()

    cur.execute(
        """
        UPDATE experiment_runs
        SET avg_retrieval_time_s = ?, avg_generation_time_s = ?, avg_total_time_s = ?
        WHERE id = ?
        """,
        (avg_ret, avg_gen, avg_tot, run_id)
    )
    conn.commit()
    conn.close()

def export_run_to_csv(run_id: int):
    """
    Export the specific run and its detail results to a CSV file.
    """
    from utils.db_schema import get_connection
    csv_path = get_csv_path()
    conn = get_connection()
    cur = conn.cursor()

    # Get Run details with explicit column select
    cur.execute(
        """
        SELECT id, timestamp, subject_id, chunking_strategy, chunk_size, chunk_overlap, 
               num_chunks, avg_chunk_len, median_chunk_len, total_tokens, indexing_time_s,
               judge_provider, judge_model, judge_temperature, judge_context_window,
               ragas_version, embedding_model
        FROM experiment_runs 
        WHERE id = ?
        """,
        (run_id,)
    )
    run_row = cur.fetchone()
    if not run_row:
        conn.close()
        return

    # Get Query details with explicit column select
    cur.execute(
        """
        SELECT run_id, timestamp, subject_id, question, answer, faithfulness, 
               answer_relevancy, context_recall, context_precision, recall_at_5, 
               recall_at_10, precision_at_5, precision_at_10, retrieval_time_s, 
               generation_time_s, total_time_s
        FROM ragas_results 
        WHERE run_id = ?
        """,
        (run_id,)
    )
    query_rows = cur.fetchall()

    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            # Write Header
            writer.writerow([
                "Run_ID", "Timestamp", "Strategy", "Chunk_Size", "Overlap", "Num_Chunks", 
                "Avg_Chunk_Len", "Median_Chunk_Len", "Total_Tokens", "Indexing_Time",
                "Question", "Answer", "Faithfulness", "Answer_Relevancy", 
                "Context_Recall", "Context_Precision", "Recall_5", "Recall_10", 
                "Precision_5", "Precision_10", "Retrieval_Time", "Generation_Time", "Total_Time",
                "Judge_Provider", "Judge_Model", "Judge_Temperature", "Judge_Context_Window",
                "Ragas_Version", "Embedding_Model"
            ])

        for q in query_rows:
            writer.writerow([
                run_row["id"],
                run_row["timestamp"],
                run_row["chunking_strategy"],
                run_row["chunk_size"],
                run_row["chunk_overlap"],
                run_row["num_chunks"],
                run_row["avg_chunk_len"],
                run_row["median_chunk_len"],
                run_row["total_tokens"],
                run_row["indexing_time_s"],
                q["question"],
                q["answer"],
                q["faithfulness"],
                q["answer_relevancy"],
                q["context_recall"],
                q["context_precision"],
                q["recall_at_5"],
                q["recall_at_10"],
                q["precision_at_5"],
                q["precision_at_10"],
                q["retrieval_time_s"],
                q["generation_time_s"],
                q["total_time_s"],
                run_row["judge_provider"],
                run_row["judge_model"],
                run_row["judge_temperature"],
                run_row["judge_context_window"],
                run_row["ragas_version"],
                run_row["embedding_model"]
            ])

    conn.close()
    print(f"[ExperimentLogger] Exported run {run_id} to {csv_path}")


def export_benchmark_to_csv(run_id: int):
    """
    Exports a benchmark run from benchmark_runs SQLite table to a CSV file benchmark_log.csv.
    """
    import csv
    import os
    from utils.db_schema import get_connection
    
    csv_dir = "data/experiments"
    os.makedirs(csv_dir, exist_ok=True)
    csv_path = os.path.join(csv_dir, "benchmark_log.csv")
    
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM benchmark_runs WHERE id = ?", (run_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return
        
    columns = [description[0] for description in cur.description]
    file_exists = os.path.exists(csv_path)
    
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(columns)
        writer.writerow([row[col] for col in columns])
        
    conn.close()
    print(f"[ExperimentLogger] Exported benchmark run {run_id} to {csv_path}")


def log_benchmark_run(state) -> int:
    """
    Logs an auto-recorded benchmark run from AgentState into the benchmark_runs SQLite table.
    Returns the newly generated run_id.
    """
    from datetime import datetime
    import sqlite3
    from utils.db_schema import get_db_path
    from utils.config import get_config
    
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    # Load embedding and generator config from YAML for context metadata
    cfg = get_config()
    emb_cfg = cfg.get("embedding", {})
    gen_cfg = cfg.get("generator_model", cfg.get("llm", {}))
    judge_cfg = cfg.get("judge_model", {})
    
    # Extracted metadata
    embedding_provider = emb_cfg.get("provider", "ollama")
    embedding_model = emb_cfg.get("model", "nomic-embed-text")
    embedding_dimension = emb_cfg.get("dimension", 768)
    
    generator_model = gen_cfg.get("model_name", gen_cfg.get("model", "qwen2.5-coder:7b"))
    generator_temperature = gen_cfg.get("temperature", 0.0)
    
    grader_model = judge_cfg.get("model_name", "qwen2.5:14b")
    grader_temperature = judge_cfg.get("temperature", 0.0)

    cur.execute(
        """
        INSERT INTO benchmark_runs (
            timestamp, question_id, query, rewritten_query, chunking_strategy, chunking_version,
            rag_mode, attempts, experiment_seed, dataset_version, prompt_template_version,
            chunk_size, chunk_overlap,
            
            git_commit_hash, machine_name, gpu_name, ram_gb, ollama_version, os_version,
            
            embedding_provider, embedding_model, embedding_dimension,
            generator_model, generator_temperature, grader_model, grader_temperature,
            
            raw_retrieved_count_l1, raw_retrieved_count_l2,
            filtered_chunk_count_l1, filtered_chunk_count_l2,
            context_chunk_count, context_char_count,
            
            retrieved_chunks_json_l1, retrieved_chunks_json_l2, final_chunks_json,
            
            hit_at_1_l1, hit_at_3_l1, hit_at_5_l1,
            recall_at_1_l1, recall_at_3_l1, recall_at_5_l1,
            
            hit_at_1_l2, hit_at_3_l2, hit_at_5_l2,
            recall_at_1_l2, recall_at_3_l2, recall_at_5_l2,
            
            first_relevant_rank_l1, first_relevant_rank_l2,
            best_similarity_l1, best_similarity_l2,
            
            grader_score_l1, grader_score_l2,
            retrieval_success_grader_l1, retrieval_success_grader_l2,
            
            rewrite_activated, final_answer,
            prompt_tokens, completion_tokens, total_tokens,
            
            retrieval_time_ms, grading_time_ms, rewrite_time_ms, generation_time_ms, total_time_ms,
            final_answer_length
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?
        )
        """,
        (
            timestamp, state.question_id, state.query, state.rewritten_query or None, state.chunking_strategy, state.chunking_version or 'v1',
            state.rag_mode, state.attempts, state.experiment_seed, state.dataset_version, state.prompt_template_version,
            state.chunk_size, state.chunk_overlap,
            
            state.git_commit_hash or None, state.machine_name or None, state.gpu_name or None, state.ram_gb, state.ollama_version or None, state.os_version or None,
            
            embedding_provider, embedding_model, embedding_dimension,
            generator_model, generator_temperature, grader_model, grader_temperature,
            
            state.raw_retrieved_count_l1, state.raw_retrieved_count_l2,
            state.filtered_chunk_count_l1, state.filtered_chunk_count_l2,
            state.context_chunk_count, state.context_char_count,
            
            state.retrieved_chunks_json_l1, state.retrieved_chunks_json_l2, state.final_chunks_json,
            
            state.hit_at_1_l1, state.hit_at_3_l1, state.hit_at_5_l1,
            state.recall_at_1_l1, state.recall_at_3_l1, state.recall_at_5_l1,
            
            state.hit_at_1_l2, state.hit_at_3_l2, state.hit_at_5_l2,
            state.recall_at_1_l2, state.recall_at_3_l2, state.recall_at_5_l2,
            
            state.first_relevant_rank_l1, state.first_relevant_rank_l2,
            state.best_similarity_l1, state.best_similarity_l2,
            
            state.grader_score_l1, state.grader_score_l2,
            state.retrieval_success_grader_l1, state.retrieval_success_grader_l2,
            
            state.rewrite_activated, state.final_answer or "",
            state.prompt_tokens, state.completion_tokens, state.total_tokens,
            
            state.retrieval_time_ms, state.grading_time_ms, state.rewrite_time_ms, state.generation_time_ms, state.total_time_ms,
            state.final_answer_length
        )
    )
    
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    # Export to CSV dynamically
    try:
        export_benchmark_to_csv(run_id)
    except Exception as e:
        print(f"[WARN] export_benchmark_to_csv failed: {e}")
        
    return run_id

