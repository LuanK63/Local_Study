import sqlite3
import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

DB_PATH = os.path.join("benchmark", "experiments", "benchmark.db")
CHARTS_DIR = os.path.join("benchmark", "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.size': 12})

def get_data():
    conn = sqlite3.connect(DB_PATH)
    
    # Get config names
    df_exp = pd.read_sql_query("""
        SELECT id as experiment_id, chunk_method, chunk_size
        FROM experiments
        WHERE status = 'DONE'
    """, conn)
    df_exp['config'] = df_exp['chunk_method'] + '_' + df_exp['chunk_size'].astype(str)
    
    # Get results
    df_res = pd.read_sql_query("SELECT * FROM experiment_results", conn)
    df = pd.merge(df_res, df_exp, on='experiment_id')
    conn.close()
    return df, df_exp

def plot_bar_metric(df, metric, title, filename):
    plt.figure(figsize=(12, 6))
    agg = df.groupby('config')[metric].mean().sort_values(ascending=False).reset_index()
    ax = sns.barplot(data=agg, x='config', y=metric, palette="viridis")
    plt.title(title, fontsize=16)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, filename))
    plt.close()

def plot_latency_distribution(df):
    plt.figure(figsize=(10, 6))
    sns.histplot(data=df, x='latency_ms', bins=30, kde=True, color='purple')
    plt.title('Overall Latency Distribution (ms)', fontsize=16)
    plt.xlabel('Latency (ms)')
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'latency_distribution.png'))
    plt.close()

def plot_boxplot_latency(df):
    plt.figure(figsize=(12, 6))
    # Sắp xếp theo median latency
    order = df.groupby('config')['latency_ms'].median().sort_values().index
    sns.boxplot(data=df, x='config', y='latency_ms', order=order, palette="Set3")
    plt.title('Latency Boxplot per Configuration', fontsize=16)
    plt.xticks(rotation=45, ha='right')
    plt.ylabel('Latency (ms)')
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'boxplot_latency.png'))
    plt.close()

def plot_breakdown(df, category, filename):
    plt.figure(figsize=(12, 6))
    agg = df.groupby([category, 'config'])['mrr'].mean().reset_index()
    
    # Để đồ thị dễ nhìn, chỉ lấy top 5 config tốt nhất tổng thể
    top_configs = df.groupby('config')['mrr'].mean().sort_values(ascending=False).head(5).index
    agg_top = agg[agg['config'].isin(top_configs)]
    
    sns.barplot(data=agg_top, x=category, y='mrr', hue='config', palette="tab10")
    plt.title(f'MRR Breakdown by {category.capitalize()} (Top 5 Configs)', fontsize=16)
    plt.ylabel('Mean Reciprocal Rank (MRR)')
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, filename))
    plt.close()

def plot_radar_chart(df):
    # Lấy top 5 cấu hình tốt nhất theo MRR
    agg = df.groupby('config')[['mrr', 'hit_at_5', 'context_recall', 'context_precision']].mean()
    top5 = agg.sort_values(by='mrr', ascending=False).head(5)
    
    metrics = top5.columns.tolist()
    N = len(metrics)
    
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    
    for idx, row in top5.iterrows():
        values = row.tolist()
        values += values[:1]
        ax.plot(angles, values, linewidth=2, linestyle='solid', label=idx)
        ax.fill(angles, values, alpha=0.1)
        
    plt.xticks(angles[:-1], metrics, size=12)
    ax.set_rlabel_position(0)
    plt.yticks([0.2, 0.4, 0.6, 0.8, 1.0], ["0.2", "0.4", "0.6", "0.8", "1.0"], color="grey", size=10)
    plt.ylim(0, 1)
    
    plt.title('Radar Chart Comparison (Top 5 Configs)', size=16, y=1.1)
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'chunking_comparison.png'))
    plt.close()

if __name__ == "__main__":
    print("Loading data...")
    df, df_exp = get_data()
    
    print("Generating hit_at_5.png...")
    plot_bar_metric(df, 'hit_at_5', 'Hit@5 by Configuration', 'hit_at_5.png')
    
    print("Generating mrr.png...")
    plot_bar_metric(df, 'mrr', 'MRR by Configuration', 'mrr.png')
    
    print("Generating latency distribution...")
    plot_latency_distribution(df)
    plot_boxplot_latency(df)
    
    print("Generating breakdowns...")
    plot_breakdown(df, 'difficulty', 'difficulty_breakdown.png')
    plot_breakdown(df, 'question_type', 'question_type_breakdown.png')
    
    print("Generating radar chart...")
    plot_radar_chart(df)
    
    print("All charts generated successfully in benchmark/charts/")
