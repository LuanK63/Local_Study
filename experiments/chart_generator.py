import os
import numpy as np

def generate_comparison_charts(results_data: dict, output_dir: str = "data/experiments/plots"):
    """
    Generate comparison bar charts with error bars (standard deviation) for each metric.
    results_data: dict of strategy_name -> dict of metric_name -> list of values
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[WARN] matplotlib is not installed. Skipping chart generation.")
        return

    os.makedirs(output_dir, exist_ok=True)
    
    strategies = list(results_data.keys())
    # Human-readable strategy names
    strategy_labels = [s.replace("_", " ").title() for s in strategies]
    
    # List of metrics to plot
    metrics = [
        ("faithfulness", "Faithfulness", "Score (0-1)"),
        ("answer_relevancy", "Answer Relevancy", "Score (0-1)"),
        ("context_recall", "Context Recall", "Score (0-1)"),
        ("context_precision", "Context Precision", "Score (0-1)"),
        ("precision_5", "Precision@5", "Score (0-1)"),
        ("precision_10", "Precision@10", "Score (0-1)"),
        ("recall_5", "Recall@5", "Score (0-1)"),
        ("recall_10", "Recall@10", "Score (0-1)"),
        ("retrieval_time_s", "Retrieval Time", "Time (seconds)"),
        ("total_time_s", "Total Response Time", "Time (seconds)")
    ]

    for metric_key, metric_title, ylabel in metrics:
        means = []
        stds = []
        
        for strategy in strategies:
            values = results_data[strategy].get(metric_key, [])
            if values:
                means.append(np.mean(values))
                stds.append(np.std(values))
            else:
                means.append(0.0)
                stds.append(0.0)
                
        plt.figure(figsize=(8, 5))
        x_pos = np.arange(len(strategies))
        
        # Draw bars with error bars
        bars = plt.bar(x_pos, means, yerr=stds, align='center', alpha=0.8, ecolor='black', capsize=10, color='#2b5c8f')
        
        plt.ylabel(ylabel)
        plt.xticks(x_pos, strategy_labels)
        plt.title(f"{metric_title} Comparison across Chunking Strategies")
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Add values on top of bars
        for bar, mean in zip(bars, means):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, height + 0.01, f'{mean:.3f}', ha='center', va='bottom', fontsize=9)
            
        plt.tight_layout()
        filename = f"{metric_key}_comparison.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath, dpi=300)
        plt.close()
        print(f"[ChartGenerator] Saved chart to {filepath}")
