import json
import sqlite3
from rapidfuzz import fuzz
from research.evaluation.relevance import evaluate_relevance

data = json.load(open('research/datasets/dsa_benchmark_v2.json', encoding='utf-8'))
q = data[0]
ref_contexts = q["reference_contexts"]

c = sqlite3.connect('data/study_agent.db')
c.row_factory = sqlite3.Row
rows = c.execute("SELECT parent_text FROM parent_chunks WHERE subject_id='dsa' AND file_path LIKE '%Hoàng%' AND parent_text LIKE '%Dijkstra%' LIMIT 5").fetchall()

for row in rows:
    chunk_text = row["parent_text"]
    print("---")
    print("MATCH?:", evaluate_relevance(ref_contexts, chunk_text))
    
    chunk_lower = chunk_text.lower()
    for ref in ref_contexts:
        ref_lower = ref.lower()
        score = fuzz.partial_ratio(ref_lower, chunk_lower)
        print("SCORE:", score)
