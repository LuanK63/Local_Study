import sys
import os
import sqlite3

# Add project root to path
sys.path.append(os.getcwd())

# Reconfigure stdout/stderr for UTF-8 on Windows
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from core.pipeline.agentic_rag import AgentState, generate_agentic_response
from utils.benchmark_loader import load_benchmark_questions, get_ground_truth_mapping
from utils.experiment_logger import log_benchmark_run
from utils.subject_loader import get_subject
from core.retrieval.hybrid_retriever import warm_up_bm25
from utils.config import get_config

def main():
    print("==================================================")
    print("STARTING PIPELINE RETRIEVAL METRICS INTEGRATION VALIDATION")
    print("==================================================")

    # 1. Warm up BM25
    print("Warming up BM25...")
    try:
        warm_up_bm25(["dsa"])
    except Exception as e:
        print(f"Warning warming up BM25: {e}")

    # 2. Load benchmark questions
    questions = load_benchmark_questions()
    print(f"Loaded {len(questions)} questions from benchmark dataset.")

    # Select 5 questions
    test_questions = questions[:5]

    # Force rag_mode to rag_grader in config
    cfg = get_config()
    if "rag" not in cfg:
        cfg["rag"] = {}
    old_rag_mode = cfg["rag"].get("mode", "pure_rag")
    cfg["rag"]["mode"] = "rag_grader"

    subject_cfg = get_subject("dsa")

    # Run each question
    for idx, q in enumerate(test_questions, 1):
        q_id = q["id"]
        query_text = q["question"]
        print(f"\n--- Running Question {idx}: ID={q_id} | Query='{query_text}' ---")

        # Initialize AgentState
        state = AgentState(
            query=query_text,
            rag_mode="rag_grader",
            chunking_strategy=cfg.get("retrieval", {}).get("chunking_strategy", "fixed"),
            question_id=q_id
        )

        # Execute response generator
        generator = generate_agentic_response(
            query=query_text,
            subject_id="dsa",
            subject_cfg=subject_cfg,
            state=state
        )

        # Consume the generator to run the pipeline
        tokens = []
        for token in generator:
            tokens.append(token)
        ans = "".join(tokens)
        state.final_answer = ans
        state.final_answer_length = len(ans)

        # Log to database
        run_id = log_benchmark_run(state)
        print(f"Logged to SQLite run_id: {run_id}")

        # Retrieve and print validation metrics
        # Format required by validation:
        # Q1 Hit@5=1 Recall@5=1.0
        # Q2 Hit@5=0 Recall@5=0.0
        # ...
        print(f"Q{idx} Hit@5={state.hit_at_5_l1} Recall@5={state.recall_at_5_l1:.1f}")
        print(f"   First Relevant Rank: {state.first_relevant_rank_l1}")

    # Restore old rag_mode
    cfg["rag"]["mode"] = old_rag_mode
    print("\n==================================================")
    print("VALIDATION COMPLETE")
    print("==================================================")

if __name__ == "__main__":
    main()
