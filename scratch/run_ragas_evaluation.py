"""
scratch/run_ragas_evaluation.py
Execute a Ragas evaluation run on the 'dsa' subject using local Ollama models.
"""
import sys
import os

# Reconfigure stdout to use UTF-8
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append("c:\\Users\\LUAN\\Desktop\\Local_Study_RAG_Agent")

from core.evaluation.ragas_eval import evaluate_pipeline
from core.retrieval.hybrid_retriever import warm_up_bm25

def main():
    subject_id = "dsa"
    
    # 1. Test dataset — 10 câu hỏi bao phủ các chủ đề DSA chính
    test_dataset = [
        # ── NGĂN XẾP (STACK) ─────────────────────────────────────────────────
        {
            "question": "ngăn xếp là gì và nguyên lý hoạt động",
            "ground_truth": (
                "Ngăn xếp (stack) là một cấu trúc dữ liệu tuyến tính hoạt động theo "
                "nguyên lý vào sau ra trước LIFO (Last In First Out). "
                "Phần tử được thêm vào sau cùng sẽ là phần tử được lấy ra đầu tiên."
            )
        },
        {
            "question": "các phép toán cơ bản trên ngăn xếp và tên gọi của chúng",
            "ground_truth": (
                "Các phép toán cơ bản trên ngăn xếp gồm: "
                "Push (đẩy một phần tử vào đỉnh ngăn xếp), "
                "Pop (lấy và loại bỏ phần tử ở đỉnh ngăn xếp), "
                "và StackInit (khởi tạo ngăn xếp rỗng)."
            )
        },

        # ── HÀNG ĐỢI (QUEUE) ─────────────────────────────────────────────────
        {
            "question": "hàng đợi là gì và sự khác biệt với ngăn xếp",
            "ground_truth": (
                "Hàng đợi (queue) là cấu trúc dữ liệu tuyến tính hoạt động theo nguyên lý "
                "vào trước ra trước FIFO (First In First Out). "
                "Phần tử được thêm vào cuối hàng (EnQueue) và lấy ra từ đầu hàng (DeQueue). "
                "Khác với ngăn xếp LIFO, hàng đợi xử lý phần tử theo thứ tự đến trước."
            )
        },

        # ── DANH SÁCH LIÊN KẾT (LINKED LIST) ──────────────────────────────────
        {
            "question": "danh sách liên kết đơn là gì và cấu trúc của một nút",
            "ground_truth": (
                "Danh sách liên kết đơn (singly linked list) là cấu trúc dữ liệu động gồm các nút "
                "liên kết với nhau theo một chiều. Mỗi nút gồm hai phần: "
                "phần dữ liệu (data) lưu giá trị, và phần liên kết (next/link) "
                "chứa địa chỉ trỏ tới nút kế tiếp. Nút cuối cùng có next = NULL."
            )
        },
        {
            "question": "so sánh danh sách liên kết đơn và danh sách liên kết đôi",
            "ground_truth": (
                "Danh sách liên kết đơn chỉ có một con trỏ next trỏ về phía sau, "
                "không thể duyệt ngược. "
                "Danh sách liên kết đôi (doubly linked list) có hai con trỏ: "
                "next (trỏ tới nút sau) và prev (trỏ tới nút trước), "
                "cho phép duyệt theo cả hai chiều nhưng tốn bộ nhớ hơn."
            )
        },

        # ── CÂY NHỊ PHÂN (BINARY TREE) ────────────────────────────────────────
        {
            "question": "cây nhị phân tìm kiếm là gì và tính chất của nó",
            "ground_truth": (
                "Cây nhị phân tìm kiếm (Binary Search Tree - BST) là cây nhị phân có tính chất: "
                "với mọi nút, tất cả giá trị ở cây con trái đều nhỏ hơn giá trị nút đó, "
                "và tất cả giá trị ở cây con phải đều lớn hơn. "
                "Tính chất này giúp tìm kiếm, thêm, xóa có độ phức tạp trung bình O(log n)."
            )
        },
        {
            "question": "các thứ tự duyệt cây nhị phân",
            "ground_truth": (
                "Có ba thứ tự duyệt cây nhị phân chính: "
                "Duyệt trước (Pre-order): gốc → trái → phải. "
                "Duyệt giữa (In-order): trái → gốc → phải — cho ra dãy tăng dần với BST. "
                "Duyệt sau (Post-order): trái → phải → gốc."
            )
        },

        # ── SẮP XẾP (SORTING) ─────────────────────────────────────────────────
        {
            "question": "thuật toán sắp xếp nhanh QuickSort hoạt động như thế nào",
            "ground_truth": (
                "QuickSort là thuật toán sắp xếp theo chiến lược chia để trị. "
                "Chọn một phần tử làm chốt (pivot), phân hoạch mảng thành hai phần: "
                "phần tử nhỏ hơn pivot ở bên trái, lớn hơn ở bên phải. "
                "Đệ quy áp dụng tương tự cho hai phần. "
                "Độ phức tạp trung bình O(n log n), trường hợp xấu nhất O(n²)."
            )
        },

        # ── TÌM KIẾM (SEARCHING) ──────────────────────────────────────────────
        {
            "question": "tìm kiếm nhị phân là gì và điều kiện áp dụng",
            "ground_truth": (
                "Tìm kiếm nhị phân (Binary Search) là thuật toán tìm kiếm trên mảng đã được sắp xếp. "
                "Mỗi bước so sánh phần tử cần tìm với phần tử giữa, "
                "nếu nhỏ hơn tìm ở nửa trái, lớn hơn tìm ở nửa phải. "
                "Điều kiện áp dụng: mảng phải được sắp xếp từ trước. "
                "Độ phức tạp O(log n)."
            )
        },

        # ── ĐỘ PHỨC TẠP THUẬT TOÁN (COMPLEXITY) ──────────────────────────────
        {
            "question": "ký hiệu Big-O là gì và dùng để làm gì",
            "ground_truth": (
                "Ký hiệu Big-O (O-lớn) là ký hiệu toán học dùng để mô tả giới hạn trên "
                "của độ phức tạp thời gian hoặc không gian của một thuật toán "
                "theo kích thước đầu vào n. "
                "Nó cho biết thuật toán 'chậm nhất có thể nhanh đến mức nào'. "
                "Ví dụ: O(1) - hằng số, O(log n) - logarit, O(n) - tuyến tính, "
                "O(n²) - bình phương."
            )
        },
    ]
    
    print(f"=== WARMING UP BM25 ===")
    warm_up_bm25([subject_id])

    print(f"\n=== RUNNING RAGAS PIPELINE EVALUATION ({len(test_dataset)} câu hỏi) ===")
    try:
        results = evaluate_pipeline(test_dataset, subject_id)
        
        print("\n" + "="*50)
        print("RAGAS EVALUATION METRICS SUMMARY")
        print("="*50)
        # Fix the dict access using the private _repr_dict or mean calculation of Ragas EvaluationResult
        for metric, score in results._repr_dict.items():
            print(f"- {metric}: {score:.4f}")
        print("="*50)
        
        # Output detailed dataframe
        import pandas as pd
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        df = results.to_pandas()
        print("\nDetailed Evaluation Table:")
        print(df[["user_input", "faithfulness", "answer_relevancy", "context_recall", "context_precision"]])
        
    except Exception as e:
        import traceback
        print(f"\n[ERROR] Evaluation failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
