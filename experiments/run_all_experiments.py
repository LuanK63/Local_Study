import os
import sys
import sqlite3
import argparse

# Add project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.chunking_comparison import run_experiment
from experiments.result_exporter import export_results_to_markdown
from experiments.chart_generator import generate_comparison_charts

def load_results_for_strategies(run_ids: dict) -> dict:
    db_path = "data/study_agent.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    results_data = {}
    for strategy, run_id in run_ids.items():
        cur = conn.cursor()
        cur.execute(
            """
            SELECT faithfulness, answer_relevancy, context_recall, context_precision,
                   recall_at_5, recall_at_10, precision_at_5, precision_at_10,
                   retrieval_time_s, total_time_s
            FROM ragas_results
            WHERE run_id = ?
            """,
            (run_id,)
        )
        rows = cur.fetchall()
        
        strategy_metrics = {
            "faithfulness": [],
            "answer_relevancy": [],
            "context_recall": [],
            "context_precision": [],
            "precision_5": [],
            "precision_10": [],
            "recall_5": [],
            "recall_10": [],
            "retrieval_time_s": [],
            "total_time_s": []
        }
        
        for r in rows:
            strategy_metrics["faithfulness"].append(r["faithfulness"] or 0.0)
            strategy_metrics["answer_relevancy"].append(r["answer_relevancy"] or 0.0)
            strategy_metrics["context_recall"].append(r["context_recall"] or 0.0)
            strategy_metrics["context_precision"].append(r["context_precision"] or 0.0)
            strategy_metrics["precision_5"].append(r["precision_at_5"] or 0.0)
            strategy_metrics["precision_10"].append(r["precision_at_10"] or 0.0)
            strategy_metrics["recall_5"].append(r["recall_at_5"] or 0.0)
            strategy_metrics["recall_10"].append(r["recall_at_10"] or 0.0)
            strategy_metrics["retrieval_time_s"].append(r["retrieval_time_s"] or 0.0)
            strategy_metrics["total_time_s"].append(r["total_time_s"] or 0.0)
            
        results_data[strategy] = strategy_metrics
        
    conn.close()
    return results_data

def main():
    parser = argparse.ArgumentParser(description="Run all chunking comparative experiments.")
    parser.add_argument("--max-questions", type=int, default=None, help="Limit number of questions to evaluate per strategy")
    parser.add_argument("--questions", type=str, default="data/evaluation/questions.json", help="Path to evaluation questions JSON file")
    args = parser.parse_args()

    print("======================================================================")
    print("STARTING ALL COMPARATIVE CHUNKING EXPERIMENTS")
    print("======================================================================")
    
    # 4 core chunking strategies to compare
    strategies = [
        {"name": "fixed", "size": 300, "overlap": 30},
        {"name": "recursive", "size": 300, "overlap": 30},
        {"name": "semantic", "size": 300, "overlap": 30}, # values will fall back/limit inside chunker
        {"name": "parent_child", "size": 300, "overlap": 30, "parent_size": 1200}
    ]
    
    run_ids = {}
    
    for s in strategies:
        print(f"\n[Main] Starting strategy: {s['name']}")
        try:
            # We use max_pages=120 to keep execution time under control
            run_id = run_experiment(
                strategy_name=s["name"],
                chunk_size=s["size"],
                chunk_overlap=s["overlap"],
                parent_size=s.get("parent_size", 1200),
                max_pages=120,
                max_questions=args.max_questions,
                questions_path=args.questions
            )
            run_ids[s["name"]] = run_id
        except Exception as e:
            print(f"[Main][ERROR] Failed running experiment for {s['name']}: {e}")
            import traceback
            traceback.print_exc()
            
    print("\n[Main] All comparative runs complete. Aggregating results...")
    
    # Load all metric data from SQLite
    results_data = load_results_for_strategies(run_ids)
    
    # Generate charts
    print("[Main] Generating comparison charts...")
    generate_comparison_charts(results_data, output_dir="data/experiments/plots")
    
    # Export summary report to Markdown
    print("[Main] Exporting summary report...")
    export_results_to_markdown(results_data, output_filepath="data/experiments/summary_report.md")
    
    print("\n======================================================================")
    print("ALL EXPERIMENTS COMPLETED SUCCESSFULLY!")
    print("======================================================================")

if __name__ == "__main__":
    # Reconfigure stdout to use UTF-8
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        
    main()
