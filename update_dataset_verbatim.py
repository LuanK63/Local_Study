import json
from core.retrieval.hybrid_retriever import search

dataset_path = 'research/datasets/dsa_benchmark_v2.json'
with open(dataset_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for q in data:
    # Build a strong query to find the exact verbatim text
    # We combine the question, the old context, and the answer to get the best match
    search_query = f"{q['question']} {q.get('reference_answer', '')} {' '.join(q.get('reference_contexts', []))}"
    
    # Search the database to find the verbatim chunk
    hits, _ = search(query=search_query, subject_id='dsa', top_k=1, mode='hybrid')
    
    if hits:
        # Replace reference_contexts with the verbatim text from the PDF
        q['reference_contexts'] = [hits[0]['text']]
    else:
        print(f"Warning: No hits found for {q['id']}")

with open(dataset_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Updated {len(data)} questions with verbatim text from the book.")
