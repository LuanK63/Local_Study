import os
import numpy as np

def format_mean_std(values: list[float], decimal_places: int = 3) -> str:
    if not values:
        return "N/A"
    mean = np.mean(values)
    std = np.std(values)
    return f"{mean:.{decimal_places}f} ± {std:.{decimal_places}f}"

def export_results_to_markdown(results_data: dict, output_filepath: str = "data/experiments/summary_report.md"):
    """
    Format results into a markdown table with Mean ± STD and save to a file.
    """
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    
    strategies = list(results_data.keys())
    
    markdown = []
    markdown.append("# Báo cáo Thử nghiệm So sánh các Chiến lược Phân mảnh (Chunking)\n")
    markdown.append("Báo cáo này trình bày kết quả so sánh hiệu năng của các phương pháp phân mảnh khác nhau trên cùng tập câu hỏi và tài liệu kiểm thử.\n")
    
    # Table Header
    markdown.append("| Chiến lược Chunking | Faithfulness | Answer Relevancy | Context Recall | Context Precision | Recall@5 | Recall@10 | Precision@5 | Precision@10 | Retrieval Time (s) | Response Time (s) |")
    markdown.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    
    for strategy in strategies:
        data = results_data[strategy]
        
        row = [
            f"**{strategy.replace('_', ' ').title()}**",
            format_mean_std(data.get("faithfulness", [])),
            format_mean_std(data.get("answer_relevancy", [])),
            format_mean_std(data.get("context_recall", [])),
            format_mean_std(data.get("context_precision", [])),
            format_mean_std(data.get("recall_5", [])),
            format_mean_std(data.get("recall_10", [])),
            format_mean_std(data.get("precision_5", [])),
            format_mean_std(data.get("precision_10", [])),
            format_mean_std(data.get("retrieval_time_s", [])),
            format_mean_std(data.get("total_time_s", []))
        ]
        markdown.append("| " + " | ".join(row) + " |")
        
    markdown_content = "\n".join(markdown)
    
    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write(markdown_content)
        
    print(f"[ResultExporter] Saved summary report to {output_filepath}")
    print("\n" + "="*80)
    print("MẠNG TỔNG HỢP KẾT QUẢ THỰC NGHIỆM:")
    print("="*80)
    print(markdown_content)
    print("="*80 + "\n")
