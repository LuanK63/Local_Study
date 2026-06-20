import csv
import json
import random
import os

def load_benchmark_questions(filepath: str = "data/experiments/benchmark_questions.csv", seed: int = 42) -> list[dict]:
    """
    Loads benchmark questions from a CSV file, parses JSON columns, shuffles them with a fixed seed
    to ensure reproducibility.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Benchmark questions CSV file not found at: {filepath}")

    questions = []
    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse ground_truth_docs (JSON array of strings)
            try:
                gt_docs = json.loads(row.get("ground_truth_docs", "[]"))
            except Exception:
                gt_docs = []
                
            # Parse ground_truth_pages (JSON array of integers)
            try:
                gt_pages = json.loads(row.get("ground_truth_pages", "[]"))
            except Exception:
                gt_pages = []
                
            # Map standard fields and provide backward-compatible keys
            item = {
                "id": int(row["id"]),
                "question": row["question"],
                "category": row["category"],
                "difficulty": row["difficulty"],
                "ground_truth_docs": gt_docs,
                "ground_truth_pages": gt_pages,
                "ground_truth_answer": row["ground_truth_answer"],
                # Backward compatibility with older evaluation keys
                "ground_truth": row["ground_truth_answer"],
                "expected_sources": [{"doc_name": d, "page_num": p} for d, p in zip(gt_docs, gt_pages)]
            }
            questions.append(item)
            
    # Shuffle deterministically
    random.seed(seed)
    random.shuffle(questions)
    return questions
