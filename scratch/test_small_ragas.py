"""
scratch/test_small_ragas.py
Small RAGAS evaluation test on 1-2 questions to verify offline functionality and metrics logging.
"""
import sys
import os
import json
import sqlite3

# Add project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ollama_check import check_ollama_status
from core.evaluation.ragas_eval import evaluate_pipeline
from utils.config import get_config

def main():
    print("[TEST] Running Ollama service and model checks...")
    check_ollama_status()
    print("[TEST] Checks passed successfully!")

    # 1. Load small test dataset
    questions_path = "data/evaluation/questions.json"
    with open(questions_path, "r", encoding="utf-8") as f:
        full_dataset = json.load(f)
    
    # Take the first 2 questions
    test_dataset = full_dataset[:2]
    print(f"[TEST] Selected {len(test_dataset)} questions for testing:")
    for idx, q in enumerate(test_dataset, 1):
        print(f"  {idx}. {q['question']}")

    # 2. Run evaluation
    subject_id = "dsa"
    run_id = 999999 # dummy run_id for testing database logs
    
    print("\n[TEST] Running evaluate_pipeline...")
    try:
        result = evaluate_pipeline(test_dataset, subject_id, run_id=run_id)
        print("\n[TEST] RAGAS Evaluation Result:")
        print(result)
        
        # 3. Check database logs
        cfg = get_config()
        db_path = cfg["database"]["path"]
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM ragas_results WHERE run_id = ?", (run_id,))
        rows = cur.fetchall()
        print(f"\n[TEST] Found {len(rows)} entries in 'ragas_results' table for run_id={run_id}:")
        for row in rows:
            print(f"  Question: '{row['question']}'")
            print(f"  Faithfulness: {row['faithfulness']}, Answer Relevancy: {row['answer_relevancy']}, Context Recall: {row['context_recall']}, Context Precision: {row['context_precision']}")
            
        # Clean up test rows
        cur.execute("DELETE FROM ragas_results WHERE run_id = ?", (run_id,))
        conn.commit()
        conn.close()
        print("[TEST] Database cleaned up successfully.")
        print("[TEST] RAGAS TEST SUCCESS!")
    except Exception as e:
        print(f"[TEST] FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
