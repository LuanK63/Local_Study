import sys
import os
import sqlite3

# Add project root to path
sys.path.append(os.getcwd())

from core.pipeline.agentic_rag import AgentState
from utils.experiment_logger import log_benchmark_run
from utils.db_schema import get_db_path

print("Starting test_benchmark_logger.py verification...")

# 1. Create mock AgentState
state = AgentState(
    query="Cây nhị phân tìm kiếm là gì?",
    rag_mode="rag_grader",
    chunking_strategy="recursive",
    question_id=999
)

# 2. Populate mock values for all key field groups
# Metadata
state.chunking_version = "v1"
state.attempts = 2
state.experiment_seed = 42
state.dataset_version = "ds_v1"
state.prompt_template_version = "prompt_v1"
state.chunk_size = 300
state.chunk_overlap = 30

# System
state.git_commit_hash = "mock_commit_123456"
state.machine_name = "MOCK-PC"
state.gpu_name = "NVIDIA GeForce RTX 4070"
state.ram_gb = 32
state.ollama_version = "0.4.1"
state.os_version = "Windows 11 Home"

# Retrieval
state.raw_retrieved_count_l1 = 5
state.raw_retrieved_count_l2 = 6
state.filtered_chunk_count_l1 = 3
state.filtered_chunk_count_l2 = 4
state.context_chunk_count = 5
state.context_char_count = 1500

# JSON
state.retrieved_chunks_json_l1 = '[{"rank": 1, "similarity": 0.85, "document": "ds.pdf", "page": 10, "chunk_id": "c1"}]'
state.retrieved_chunks_json_l2 = '[{"rank": 1, "similarity": 0.90, "document": "ds.pdf", "page": 11, "chunk_id": "c2"}]'
state.final_chunks_json = '[{"rank": 1, "similarity": 0.90, "document": "ds.pdf", "page": 11, "chunk_id": "c2"}]'

# Ground Truth Metrics
state.hit_at_1_l1 = 1
state.hit_at_3_l1 = 1
state.hit_at_5_l1 = 1
state.recall_at_1_l1 = 0.5
state.recall_at_3_l1 = 0.5
state.recall_at_5_l1 = 1.0

state.hit_at_1_l2 = 1
state.hit_at_3_l2 = 1
state.hit_at_5_l2 = 1
state.recall_at_1_l2 = 0.5
state.recall_at_3_l2 = 0.5
state.recall_at_5_l2 = 1.0

state.first_relevant_rank_l1 = 1
state.first_relevant_rank_l2 = 1

# Similarity
state.best_similarity_l1 = 0.85
state.best_similarity_l2 = 0.90

# Grader
state.grader_score_l1 = 4
state.grader_score_l2 = 5
state.retrieval_success_grader_l1 = 1
state.retrieval_success_grader_l2 = 1

# Agent
state.rewrite_activated = 1

# Answer
state.final_answer = "Cây nhị phân tìm kiếm là một cấu trúc dữ liệu..."
state.final_answer_length = len(state.final_answer)

# Tokens
state.prompt_tokens = 250
state.completion_tokens = 120
state.total_tokens = 370

# Latency
state.retrieval_time_ms = 45.5
state.grading_time_ms = 120.3
state.rewrite_time_ms = 250.1
state.generation_time_ms = 1100.8
state.total_time_ms = 1516.7

# 3. Call log_benchmark_run()
print("Logging benchmark run to database...")
run_id = log_benchmark_run(state)
print("Log successful! Inserted run_id:", run_id)

# 4. Read back from SQLite
db_path = get_db_path()
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT * FROM benchmark_runs WHERE id = ?", (run_id,))
row = cur.fetchone()
conn.close()

if not row:
    print("ERROR: Failed to read row from database!")
    sys.exit(1)

# Map row indices to column names
columns = [
    "id", "timestamp", "question_id", "query", "rewritten_query", "chunking_strategy", "chunking_version",
    "rag_mode", "attempts", "experiment_seed", "dataset_version", "prompt_template_version",
    "chunk_size", "chunk_overlap", "git_commit_hash", "machine_name", "gpu_name", "ram_gb",
    "ollama_version", "os_version", "embedding_provider", "embedding_model", "embedding_dimension",
    "generator_model", "generator_temperature", "grader_model", "grader_temperature",
    "raw_retrieved_count_l1", "raw_retrieved_count_l2", "filtered_chunk_count_l1", "filtered_chunk_count_l2",
    "context_chunk_count", "context_char_count", "retrieved_chunks_json_l1", "retrieved_chunks_json_l2",
    "final_chunks_json", "hit_at_1_l1", "hit_at_3_l1", "hit_at_5_l1", "recall_at_1_l1", "recall_at_3_l1",
    "recall_at_5_l1", "hit_at_1_l2", "hit_at_3_l2", "hit_at_5_l2", "recall_at_1_l2", "recall_at_3_l2",
    "recall_at_5_l2", "first_relevant_rank_l1", "first_relevant_rank_l2", "best_similarity_l1",
    "best_similarity_l2", "grader_score_l1", "grader_score_l2", "retrieval_success_grader_l1",
    "retrieval_success_grader_l2", "rewrite_activated", "final_answer", "prompt_tokens",
    "completion_tokens", "total_tokens", "retrieval_time_ms", "grading_time_ms", "rewrite_time_ms",
    "generation_time_ms", "total_time_ms", "final_answer_length"
]

row_dict = dict(zip(columns, row))

# 5. Print results
print("\n=== Validation output ===")
print("Inserted Run ID:     ", row_dict["id"])
print("Question ID:         ", row_dict["question_id"])
print("RAG Mode:            ", row_dict["rag_mode"])
print("Chunking Strategy:   ", row_dict["chunking_strategy"])
print("Hit@5 L1:            ", row_dict["hit_at_5_l1"])
print("Recall@5 L1:         ", row_dict["recall_at_5_l1"])
print("=========================")

print("Verification complete.")
