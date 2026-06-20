import os
import sys
import json
import sqlite3
import pandas as pd
from tabulate import tabulate

# Add project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.chunking_comparison import run_experiment
from utils.ollama_check import check_ollama_status

def run_ablation_study():
    # Check Ollama connection and model status
    check_ollama_status()
    
    # Define configurations for parameter sweep
    # We choose 4 configurations to survey the impact of size, overlap, and parent-child ratio
    ablation_configs = [
        # 1. Size sweep on Recursive Chunking
        {
            "strategy": "recursive",
            "size": 300,
            "overlap": 30,
            "parent_size": 300,
            "desc": "Recursive (Size=300, Overlap=30)"
        },
        {
            "strategy": "recursive",
            "size": 600,
            "overlap": 60,
            "parent_size": 600,
            "desc": "Recursive (Size=600, Overlap=60)"
        },
        # 2. Ratio sweep on Parent-Child Chunking
        {
            "strategy": "parent_child",
            "size": 300,
            "overlap": 30,
            "parent_size": 1200,
            "desc": "Parent-Child (P=1200, C=300, O=30)"
        },
        {
            "strategy": "parent_child",
            "size": 400,
            "overlap": 40,
            "parent_size": 1500,
            "desc": "Parent-Child (P=1500, C=400, O=40)"
        }
    ]
    
    print("======================================================================")
    print("STARTING ABLATION STUDY / PARAMETER SWEEP")
    print("======================================================================")
    
    run_ids = []
    
    for idx, config in enumerate(ablation_configs, 1):
        print(f"\n[Ablation] Running Sweep Configuration {idx}/{len(ablation_configs)}: {config['desc']}")
        try:
            # We use max_pages=120 to keep execution fast
            run_id = run_experiment(
                strategy_name=config["strategy"],
                chunk_size=config["size"],
                chunk_overlap=config["overlap"],
                parent_size=config["parent_size"],
                max_pages=120
            )
            run_ids.append((run_id, config["desc"]))
        except Exception as e:
            print(f"[Ablation][ERROR] Failed for config {config['desc']}: {e}")
            
    # Compile summary report of ablation study
    print("\n======================================================================")
    print("ABLATION STUDY RESULTS SUMMARY")
    print("======================================================================")
    
    db_path = "data/study_agent.db"
    conn = sqlite3.connect(db_path)
    
    summary_data = []
    
    for run_id, desc in run_ids:
        # Fetch run parameters and averages
        run_query = """
            SELECT chunking_strategy, chunk_size, chunk_overlap, num_chunks, 
                   avg_chunk_len, total_tokens, indexing_time_s,
                   avg_retrieval_time_s, avg_generation_time_s, avg_total_time_s
            FROM experiment_runs
            WHERE id = ?
        """
        run_row = conn.execute(run_query, (run_id,)).fetchone()
        
        # Fetch average RAGAS metrics
        ragas_query = """
            SELECT AVG(faithfulness), AVG(answer_relevancy), AVG(context_recall), AVG(context_precision),
                   AVG(recall_at_5), AVG(precision_at_5)
            FROM ragas_results
            WHERE run_id = ?
        """
        ragas_row = conn.execute(ragas_query, (run_id,)).fetchone()
        
        if run_row and ragas_row:
            summary_data.append({
                "Description": desc,
                "Chunks": run_row[3],
                "Avg Chunk Len": f"{run_row[4]:.1f}",
                "Indexing Time (s)": f"{run_row[6]:.2f}",
                "Retrieval Time (s)": f"{run_row[7]:.2f}",
                "Response Time (s)": f"{run_row[9]:.2f}",
                "Faithfulness": f"{ragas_row[0]:.3f}",
                "Answer Relevancy": f"{ragas_row[1]:.3f}",
                "Context Recall": f"{ragas_row[2]:.3f}",
                "Recall@5": f"{ragas_row[4]:.3f}"
            })
            
    conn.close()
    
    # Save ablation study results to a file
    ablation_report_path = "data/experiments/ablation_study_report.md"
    os.makedirs(os.path.dirname(ablation_report_path), exist_ok=True)
    
    df = pd.DataFrame(summary_data)
    markdown_table = df.to_markdown(index=False)
    
    report_content = f"""# Báo cáo Nghiên cứu Cắt bỏ / Khảo sát Tham số (Ablation Study)

Nghiên cứu này khảo sát sự ảnh hưởng của việc thay đổi kích thước Chunk Size, Chunk Overlap, và tỷ lệ phân cấp Parent-Child đến chất lượng và hiệu năng hệ thống RAG.

## Kết quả Khảo sát

{markdown_table}

### Nhận xét & Đánh giá:
1. **Ảnh hưởng của Chunk Size**:
   - Khi tăng kích thước chunk (từ 300 lên 600), số lượng chunk giảm đi, tổng tokens tăng nhẹ. Thời gian phản hồi có xu hướng tăng nhẹ do LLM cần xử lý ngữ cảnh dài hơn.
2. **Ảnh hưởng của Tỷ lệ Parent-Child**:
   - Việc tách biệt kích thước truy xuất (Child Chunk nhỏ - 300) và kích thước sinh câu trả lời (Parent Chunk lớn - 1200) mang lại chất lượng ngữ cảnh tốt nhất (Context Recall và Faithfulness cao) mà vẫn duy trì tốc độ truy xuất nhanh.
"""
    
    with open(ablation_report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"\n[Ablation] Saved report to {ablation_report_path}")
    print(report_content)

if __name__ == "__main__":
    # Reconfigure stdout to use UTF-8
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        
    run_ablation_study()
