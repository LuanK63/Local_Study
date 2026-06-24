import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join("benchmark", "experiments", "benchmark.db")
REPORTS_DIR = os.path.join("benchmark", "reports")
CHARTS_DIR = os.path.join("benchmark", "charts")

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

def generate_aggregate_results():
    conn = sqlite3.connect(DB_PATH)
    
    # Lấy thông tin cơ bản từ experiments
    df_exp = pd.read_sql_query("""
        SELECT id as experiment_id, chunk_method, chunk_size, avg_latency_ms, median_latency_ms
        FROM experiments
        WHERE status = 'DONE'
    """, conn)
    
    # Tính toán aggregates từ experiment_results
    df_res = pd.read_sql_query("""
        SELECT 
            experiment_id,
            AVG(hit_at_5) as hit_at_5,
            AVG(mrr) as mrr,
            AVG(context_recall) as context_recall,
            AVG(context_precision) as context_precision
        FROM experiment_results
        GROUP BY experiment_id
    """, conn)
    
    # Merge
    df_agg = pd.merge(df_exp, df_res, on='experiment_id')
    
    # Thêm cột configuration cho dễ nhìn
    df_agg['configuration'] = df_agg['chunk_method'] + '_' + df_agg['chunk_size'].astype(str)
    
    # Sắp xếp các cột
    cols = ['configuration', 'chunk_method', 'chunk_size', 'hit_at_5', 'mrr', 'context_recall', 'context_precision', 'avg_latency_ms', 'median_latency_ms']
    df_agg = df_agg[cols]
    
    # Xuất ra CSV
    csv_path = os.path.join(REPORTS_DIR, 'aggregate_results.csv')
    df_agg.to_csv(csv_path, index=False)
    print(f"Generated {csv_path}")
    
    return df_agg

def generate_ranking_summary(df_agg):
    md_path = os.path.join(REPORTS_DIR, 'ranking_summary.md')
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# Benchmark Ranking Summary\n\n")
        f.write("Baseline: Fixed Chunking 512\n\n")
        
        metrics = [
            ('MRR', 'mrr', False),
            ('Hit@5', 'hit_at_5', False),
            ('Context Recall', 'context_recall', False),
            ('Avg Latency (ms)', 'avg_latency_ms', True)
        ]
        
        for name, col, ascending in metrics:
            f.write(f"## Top 3 by {name}\n")
            top3 = df_agg.sort_values(by=col, ascending=ascending).head(3)
            for idx, row in top3.iterrows():
                f.write(f"- **{row['configuration']}**: {row[col]:.4f}\n")
            f.write("\n")
            
        # Descriptive Statistics
        f.write("## Descriptive Statistics (All Configurations)\n\n")
        desc_stats = df_agg[['hit_at_5', 'mrr', 'context_recall', 'context_precision', 'avg_latency_ms', 'median_latency_ms']].describe()
        f.write(desc_stats.to_markdown())
        f.write("\n")
        
    print(f"Generated {md_path}")

if __name__ == "__main__":
    df_agg = generate_aggregate_results()
    generate_ranking_summary(df_agg)
