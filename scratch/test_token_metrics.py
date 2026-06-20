"""
scratch/test_token_metrics.py
Phase 16 Validation: Token Metrics Integration
Chay 5 cau benchmark, in prompt_tokens / completion_tokens / total_tokens.
"""
import sys
import os
import sqlite3
import csv

# Fix Windows console encoding
if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.append(os.getcwd())

from core.pipeline.agentic_rag import AgentState, generate_agentic_response
from utils.benchmark_loader import load_benchmark_questions
from utils.subject_loader import get_subject
from core.retrieval.hybrid_retriever import warm_up_bm25
from utils.config import get_config
from utils.db_schema import get_db_path

def main():
    print("=" * 60)
    print("PHASE 16 VALIDATION: Token Metrics Integration")
    print("=" * 60)

    db_path  = get_db_path()
    csv_path = os.path.join("data", "experiments", "benchmark_log.csv")

    # Warm up BM25
    print("\n[INFO] Warming up BM25...")
    try:
        warm_up_bm25(["dsa"])
    except Exception as e:
        print(f"[WARN] BM25 warm-up: {e}")

    # Load 5 questions
    questions = load_benchmark_questions()[:5]
    print(f"[INFO] Loaded {len(questions)} benchmark questions\n")

    cfg        = get_config()
    subject_id  = "dsa"
    subject_cfg = get_subject(subject_id)
    chunking_strategy = cfg.get("retrieval", {}).get("chunking_strategy", "fixed")

    results = []

    for idx, q in enumerate(questions, 1):
        qid        = q.get("id", idx)
        query_text = q.get("question", "")
        gt_docs    = q.get("ground_truth_docs", [])
        gt_pages   = q.get("ground_truth_pages", [])

        print(f"{'='*60}")
        print(f"Question {idx} (id={qid}): {query_text[:70]}...")

        state = AgentState(
            query             = query_text,
            rag_mode          = "pure_rag",
            chunking_strategy = chunking_strategy,
            question_id       = qid,
        )

        try:
            gen = generate_agentic_response(
                query       = query_text,
                subject_id  = subject_id,
                subject_cfg = subject_cfg,
                state       = state,
                gt_docs     = gt_docs,
                gt_pages    = gt_pages,
            )
            # Consume generator
            for _ in gen:
                pass
        except Exception as e:
            import traceback
            print(f"  [ERROR] Pipeline failed: {traceback.format_exc()}")
            continue

        pt = state.prompt_tokens
        ct = state.completion_tokens
        tt = state.total_tokens

        print(f"  Prompt Tokens    : {pt}")
        print(f"  Completion Tokens: {ct}")
        print(f"  Total Tokens     : {tt}")

        expected = pt + ct
        check = "OK" if tt == expected else "FAIL"
        print(f"  Sum Check        : {check}  ({pt} + {ct} = {expected})")

        if tt == 0:
            print(f"  [WARN] total_tokens = 0 -- Ollama returned no token metadata")

        results.append({"idx": idx, "qid": qid, "pt": pt, "ct": ct, "tt": tt})

    # ── SQLite Check ────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("[SQLite] Last 5 rows: prompt_tokens, completion_tokens, total_tokens")
    try:
        conn = sqlite3.connect(db_path)
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, question_id, prompt_tokens, completion_tokens, total_tokens
            FROM benchmark_runs
            ORDER BY id DESC
            LIMIT 5
        """)
        rows = cur.fetchall()
        conn.close()

        print(f"  {'ID':<6} {'QID':<10} {'PT':>8} {'CT':>8} {'TT':>8}  Check")
        print(f"  {'-'*50}")
        all_nonzero = True
        for row in rows:
            rid, qid_db, pt, ct, tt = row
            pt, ct, tt = pt or 0, ct or 0, tt or 0
            expected   = pt + ct
            ok         = "OK" if tt == expected else "FAIL"
            if pt == 0 and ct == 0:
                all_nonzero = False
            print(f"  {rid:<6} {str(qid_db):<10} {pt:>8} {ct:>8} {tt:>8}  {ok}")

        if all_nonzero:
            print("\n  [PASS] Khong con toan so 0 trong SQLite")
        else:
            print("\n  [WARN] Co dong token = 0 trong SQLite (Ollama co the khong tra metadata)")
    except Exception as e:
        print(f"  [ERROR] SQLite check failed: {e}")

    # ── CSV Check ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"[CSV] {csv_path}")
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader   = csv.DictReader(f)
            csv_rows = list(reader)

        last5 = csv_rows[-5:]
        print(f"  {'ID':<6} {'PT':>8} {'CT':>8} {'TT':>8}")
        print(f"  {'-'*36}")
        for row in last5:
            rid = row.get("id", "?")
            pt  = int(row.get("prompt_tokens", 0) or 0)
            ct  = int(row.get("completion_tokens", 0) or 0)
            tt  = int(row.get("total_tokens", 0) or 0)
            print(f"  {rid:<6} {pt:>8} {ct:>8} {tt:>8}")
    except FileNotFoundError:
        print("  [WARN] benchmark_log.csv not found")
    except Exception as e:
        print(f"  [ERROR] CSV check failed: {e}")

    print(f"\n{'='*60}")
    print("[DONE] Phase 16 Token Metrics Validation complete.")

if __name__ == "__main__":
    main()
