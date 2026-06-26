"""
research/report_generator.py
=============================
Xuất kết quả benchmark từ SQLite ra CSV, Excel và biểu đồ so sánh.
"""
import sqlite3
import os
import sys

def get_db_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "data", "benchmark_logs.db")

def generate_report(output_dir="artifacts/reports"):
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # --- Lấy kết quả tổng hợp ---
    query = """
        SELECT
            e.config_name,
            e.dataset_version,
            e.status,
            b.total_questions,
            ROUND(b.precision_at_5, 4)   AS precision_at_5,
            ROUND(b.recall_at_5, 4)       AS recall_at_5,
            ROUND(b.f1_at_5, 4)           AS f1_at_5,
            ROUND(b.hit_rate_at_5, 4)     AS hit_rate_at_5,
            ROUND(b.mrr, 4)               AS mrr,
            ROUND(b.retrieval_latency, 1) AS avg_latency_ms
        FROM experiments e
        JOIN benchmark_results b ON e.experiment_id = b.experiment_id
        ORDER BY b.mrr DESC
    """
    rows = conn.execute(query).fetchall()
    conn.close()

    if not rows:
        print("[WARN] Không có dữ liệu trong database.")
        sys.exit(1)

    # Chuyển sang list of dict
    data = [dict(r) for r in rows]

    # --- In ra console ---
    print("\n" + "="*90)
    print(f"{'Config':<30} {'Precision@5':>12} {'Recall@5':>10} {'F1@5':>8} {'HitRate@5':>11} {'MRR':>8} {'Latency(ms)':>12}")
    print("-"*90)
    for d in data:
        print(f"{d['config_name']:<30} {d['precision_at_5']:>12.4f} {d['recall_at_5']:>10.4f} {d['f1_at_5']:>8.4f} {d['hit_rate_at_5']:>11.4f} {d['mrr']:>8.4f} {d['avg_latency_ms']:>12.1f}")
    print("="*90)

    # --- Xuất CSV ---
    try:
        import pandas as pd
        df = pd.DataFrame(data)
        csv_path = os.path.join(output_dir, "benchmark_summary.csv")
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"\n[OK] CSV: {csv_path}")

        # --- Xuất Excel ---
        try:
            excel_path = os.path.join(output_dir, "benchmark_summary.xlsx")
            df.to_excel(excel_path, index=False, engine='openpyxl')
            print(f"[OK] Excel: {excel_path}")
        except Exception as e:
            print(f"[WARN] Không xuất được Excel: {e}")

        # --- Vẽ biểu đồ ---
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import numpy as np

            metrics = ['precision_at_5', 'recall_at_5', 'f1_at_5', 'hit_rate_at_5', 'mrr']
            labels  = ['Precision@5', 'Recall@5', 'F1@5', 'HitRate@5', 'MRR']
            configs = [d['config_name'] for d in data]
            n_metrics = len(metrics)
            n_configs = len(configs)

            x = np.arange(n_metrics)
            width = 0.8 / n_configs

            fig, ax = plt.subplots(figsize=(14, 7))
            colors = ['#4C72B0', '#DD8452', '#55A868', '#C44E52', '#8172B2', '#937860']

            for i, d in enumerate(data):
                vals = [d[m] for m in metrics]
                offset = (i - n_configs / 2 + 0.5) * width
                bars = ax.bar(x + offset, vals, width, label=d['config_name'], color=colors[i % len(colors)], alpha=0.85)
                for bar, val in zip(bars, vals):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.008,
                            f'{val:.3f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

            ax.set_xlabel('Metric', fontsize=12)
            ax.set_ylabel('Score (0–1)', fontsize=12)
            ax.set_title('Benchmark Retrieval Metrics — Chunking Strategy Comparison', fontsize=14, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(labels, fontsize=11)
            ax.set_ylim(0, 1.1)
            ax.legend(title='Chunking Config', fontsize=10)
            ax.grid(axis='y', linestyle='--', alpha=0.5)
            plt.tight_layout()

            chart_path = os.path.join(output_dir, "benchmark_metrics_chart.png")
            plt.savefig(chart_path, dpi=150)
            print(f"[OK] Chart: {chart_path}")
        except Exception as e:
            print(f"[WARN] Không vẽ được biểu đồ: {e}")

    except ImportError:
        print("[WARN] pandas không được cài đặt. Chỉ in ra console.")


if __name__ == "__main__":
    generate_report()
