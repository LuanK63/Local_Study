import sys
from pathlib import Path

# Khắc phục lỗi UnicodeEncodeError trên terminal Windows
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from utils.config import get_config
from core.document_processor.pdf_reader import read_pdf
from core.document_processor.chunking.factory import get_chunker

TEST_FILE = Path("subjects/dsa/documents/test.pdf")
OUTPUT_FILE = Path("research/chunking_inspection.txt")

if not TEST_FILE.exists():
    print(f"[ERROR] Không tìm thấy file PDF mẫu tại: {TEST_FILE.resolve()}")
    sys.exit(1)

# Đọc tài liệu PDF
print("[1/3] Đang đọc tài liệu PDF...")
pages = read_pdf(TEST_FILE)

CONFIGS = [
    # 1. Fixed
    ("fixed_512", "fixed", 512, 100, {"length_unit": "char"}),
    # 2. Recursive
    ("recursive_512", "recursive", 512, 100, {"length_unit": "char"}),
    # 3. Token
    ("token_256", "token", 256, 50, {}),
    # 4. Sentence
    ("sentence_5_1", "sentence", None, None, {"sentence_count": 5, "overlap_sentences": 1}),
    # 5. Paragraph
    ("paragraph_1_0", "paragraph", None, None, {"paragraphs_per_chunk": 1, "overlap_paragraphs": 0}),
    # 6. Semantic
    ("semantic_1_2", "semantic", 300, 0, {"semantic_threshold_factor": 1.2}),
    # 7. Parent-Child
    ("parent_child_1200_300", "parent_child", 300, 30, {
        "parent_chunk_size": 1200,
        "child_chunk_size": 300,
        "child_chunk_overlap": 30
    }),
]

print("[2/3] Đang phân tích và cắt thử nghiệm...")
report_lines = []
report_lines.append("=" * 80)
report_lines.append("BÁO CÁO CHI TIẾT KẾT QUẢ CHIA CHUNK (7 PHƯƠNG PHÁP)")
report_lines.append("File kiểm thử: " + TEST_FILE.name)
report_lines.append("=" * 80 + "\n")

for name, strategy, size, overlap, extra in CONFIGS:
    report_lines.append("=" * 80)
    report_lines.append(f"PHƯƠNG PHÁP: {name.upper()}")
    report_lines.append("=" * 80)

    cfg = get_config()["retrieval"]
    cfg["chunking_strategy"] = strategy
    cfg["chunk_size"] = size
    cfg["chunk_overlap"] = overlap
    for key, val in extra.items():
        cfg[key] = val

    chunker = get_chunker()
    parent_chunks = chunker.split_documents(pages)

    if strategy == "parent_child":
        report_lines.append(f"Tổng số Parent Chunks: {len(parent_chunks)}")
        total_children = sum(len(p.children) for p in parent_chunks)
        report_lines.append(f"Tổng số Child Chunks: {total_children}")
        report_lines.append("-" * 50)
        
        # Chỉ in thử nghiệm 2 Parent Chunks đầu tiên và các con của chúng
        for i, parent in enumerate(parent_chunks[:2], 1):
            report_lines.append(f"\n[PARENT CHUNK {i}] - ID: {parent.parent_id}")
            report_lines.append(f"--- NỘI DUNG CHA (Độ dài: {len(parent.text)} ký tự) ---")
            report_lines.append(parent.text)
            report_lines.append("-" * 30)
            for j, child in enumerate(parent.children, 1):
                report_lines.append(f" └─ [Child Chunk {i}.{j}] (Độ dài: {len(child.text)} ký tự):")
                report_lines.append(f" \"{child.text[:150]}...\"")
            report_lines.append("-" * 50)
    else:
        report_lines.append(f"Tổng số Chunks: {len(parent_chunks)}")
        report_lines.append("-" * 50)
        
        # Chỉ in 3 Chunks đầu tiên để kiểm tra cấu hình
        for i, parent in enumerate(parent_chunks[:3], 1):
            text = parent.text
            report_lines.append(f"\n[CHUNK {i}] (Độ dài: {len(text)} ký tự):")
            report_lines.append(text)
            report_lines.append("-" * 50)

    report_lines.append("\n\n")

print("[3/3] Đang ghi báo cáo ra file...")
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print(f"[OK] Đã xuất báo cáo chi tiết về cách chia chunk ra file: {OUTPUT_FILE.resolve()}")
