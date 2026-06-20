"""
core/document_processor/pdf_reader.py
Extract text + metadata from PDF files using PyMuPDF (primary) / pdfplumber (fallback).
No page limit — suitable for large books (1000+ pages).

Page numbering:
  Ưu tiên extract PRINTED page number từ header '\ 64 ^' trong text.
  Fallback về physical page (1-indexed) nếu không detect được.
  Skip trang front matter (header Roman numeral như '] ii ^').
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Generator, Callable
import re
import fitz  # PyMuPDF

# Pattern detect printed page number trong text header
_PRINTED_PAGE_RE = re.compile(r']\s*(\d{1,4})\s*\^')
_ROMAN_RE        = re.compile(r']\s*([ivxlcdmIVXLCDM]+)\s*\^')


def clean_ocr_duplicates(text: str) -> str:
    """
    Dự án gặp lỗi trích xuất lặp ký tự (bold/shadowing effect) dạng:
    "LLÊÊM MIINNH HHOÀ HOÀNNG G" -> "LÊ MINH HOÀNG"
    "PPH HẦẦNN22..CCẤẤUUTTRRÚÚCCDDỮ ỮLLIIỆỆUUVVÀÀ" -> "PHẦN 2. CẤU TRÚC DỮ LIỆU VÀ"
    """
    if not text:
        return text

    def clean_word(word: str) -> str:
        if len(word) <= 1:
            return word
            
        # Đếm số lượng cặp ký tự lặp liền kề
        dup_pairs = 0
        k = 0
        while k < len(word) - 1:
            if word[k].lower() == word[k+1].lower():
                dup_pairs += 1
                k += 2
            else:
                k += 1
                
        # Kiểm tra xem có ký tự tiếng Việt có dấu nào bị lặp không
        has_accent_dup = False
        for j in range(len(word)-1):
            if word[j].lower() == word[j+1].lower() and any(c in "àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ" for c in word[j].lower()):
                has_accent_dup = True
                break
                
        # Kiểm tra xem cặp lặp duy nhất là 'e' hoặc 'o' (English double letters)
        is_common_english_dup = False
        if dup_pairs == 1:
            for j in range(len(word)-1):
                if word[j].lower() == word[j+1].lower() and word[j].lower() in "eo":
                    is_common_english_dup = True
                    break
                    
        dup_ratio = (dup_pairs * 2) / len(word)
        
        should_clean = False
        if has_accent_dup:
            should_clean = True
        elif dup_pairs >= 2:
            should_clean = True
        elif dup_pairs == 1 and len(word) <= 4 and dup_ratio >= 0.5 and not is_common_english_dup:
            should_clean = True
            
        if should_clean:
            cleaned = []
            skip = False
            for j in range(len(word)):
                if skip:
                    skip = False
                    continue
                if j + 1 < len(word) and word[j].lower() == word[j+1].lower():
                    cleaned.append(word[j])
                    skip = True
                else:
                    cleaned.append(word[j])
            return "".join(cleaned)
        return word

    # Clean words
    words = text.split()
    cleaned_words = [clean_word(w) for w in words]
    result = " ".join(cleaned_words)
    
    # Khử các ký tự lặp cách quãng ngắn (ví dụ: "G G" -> "G")
    for _ in range(3):
        result = re.sub(r'\b([A-Za-zÀ-ỹđĐ])\s+\1\b', r'\1', result)
        
    return result


def _extract_printed_page(text: str) -> int | None:
    """
    Extract printed/visual page number từ text header của trang.
    Ví dụ: '] 64 ^  Chuyên đề' → 64

    Trả về None nếu:
      - Trang front matter ('] ii ^' — Roman numeral)
      - Không tìm thấy pattern
    """
    first = text[:400]  # Chỉ check 400 chars đầu
    # Front matter: Roman numeral và không có số Arabic
    if _ROMAN_RE.search(first) and not _PRINTED_PAGE_RE.search(first):
        return None
    m = _PRINTED_PAGE_RE.search(first)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 9999:
            return n
    return None


@dataclass
class PageContent:
    page_num: int          # 1-indexed
    text: str
    file_path: str
    word_boxes: list = field(default_factory=list)


def _extract_page_as_markdown(page: fitz.Page) -> str:
    """
    Trích xuất nội dung của trang PDF dưới dạng Markdown bằng cách phân tích 
    font size và font flags của các spans văn bản để xác định các Heading.
    Đồng thời nhận diện tiêu đề dạng chương/mục thông thường bằng Regex.
    """
    try:
        blocks = page.get_text("dict")["blocks"]
    except Exception:
        # Fallback về text thường nếu có lỗi lấy dict
        return page.get_text("text")
        
    page_lines = []
    
    # Một số Regex nhận diện tiêu đề chương mục phổ biến
    ch_pattern = re.compile(r'^(chương\s+\d+|chương\s+[ivxlcdm]+)\b', re.IGNORECASE)
    sec_pattern = re.compile(r'^\d+(\.\d+){1,3}\b')
    
    for block in blocks:
        if "lines" not in block:
            continue
            
        block_text_parts = []
        is_heading = False
        heading_level = 0
        
        # Duyệt qua từng dòng trong block
        for line in block["lines"]:
            line_text_parts = []
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                size = span["size"]
                flags = span["flags"]
                is_bold = bool(flags & 2)  # fitz flag: 2 = Bold
                
                # Quyết định mức độ Header dựa trên cỡ chữ (heuristic phù hợp đa số tài liệu học tập)
                if size >= 15.5:
                    is_heading = True
                    heading_level = max(heading_level, 1)
                elif size >= 12.5 and is_bold:
                    is_heading = True
                    heading_level = max(heading_level, 2)
                elif size >= 11.0 and is_bold:
                    is_heading = True
                    heading_level = max(heading_level, 3)
                
                line_text_parts.append(span["text"])
            
            if line_text_parts:
                line_text = "".join(line_text_parts).strip()
                if line_text:
                    block_text_parts.append(line_text)
                    
        if not block_text_parts:
            continue
            
        block_content = " ".join(block_text_parts).strip()
        
        # Áp dụng Regex bổ sung nếu block_content bắt đầu bằng ký hiệu chương mục đặc trưng
        if not is_heading:
            if ch_pattern.match(block_content):
                is_heading = True
                heading_level = 1
            elif sec_pattern.match(block_content):
                # Đếm số dấu chấm để quyết định cấp độ tiêu đề
                # ví dụ: "1.1" có 1 dấu chấm -> Header 2; "1.1.1" có 2 dấu chấm -> Header 3
                dots = block_content.split()[0].count(".")
                if dots == 1:
                    is_heading = True
                    heading_level = 2
                elif dots >= 2:
                    is_heading = True
                    heading_level = 3
                    
        # Định dạng dòng văn bản cuối cùng của block
        if is_heading and heading_level > 0:
            hashes = "#" * heading_level
            # Đảm bảo không bị lặp lại dấu # nếu text đã bắt đầu bằng #
            clean_text = block_content.lstrip("#").strip()
            page_lines.append(f"\n{hashes} {clean_text}\n")
        else:
            page_lines.append(block_content)
            
    # Gộp các block lại thành văn bản hoàn chỉnh của trang
    text_out = "\n".join(page_lines).strip()
    return text_out if text_out else page.get_text("text")


def read_pdf(
    file_path: str | Path,
    progress_cb: Callable[[int, int], None] | None = None,
    max_pages: int | None = None,
) -> list[PageContent]:
    """
    Extract all pages from a PDF. No page limit.
    progress_cb(current_page, total_pages) called every 50 pages.
    Uses PyMuPDF (fast). Falls back to pdfplumber only if fitz fails.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    pages = []

    # Strategy 1: PyMuPDF — fast, low memory, handles large PDFs
    try:
        doc = fitz.open(str(path))
        total = doc.page_count
        limit = min(total, max_pages) if max_pages is not None else total
        for i in range(limit):
            page = doc[i]
            raw_text = page.get_text("text")
            if not raw_text.strip():
                continue
            # Ưu tiên printed page number; bỏ qua trang front matter Roman numeral
            printed = _extract_printed_page(raw_text)
            physical = i + 1
            # Skip trang front matter nếu detect được Roman numeral header
            # (chúng chứa TOC entries, gây nhiễu BM25)
            if printed is None and _ROMAN_RE.search(raw_text[:300]):
                continue   # bỏ qua front matter
            
            # Trích xuất văn bản có định dạng Markdown cấu trúc
            markdown_text = _extract_page_as_markdown(page)
            
            # Chuẩn hóa Unicode sang dạng NFC để tránh lỗi NFD/NFC mismatch khi tìm kiếm RAG
            import unicodedata
            markdown_text = unicodedata.normalize('NFC', markdown_text)
            
            # Làm sạch các ký tự bị lặp do lỗi OCR/Double-printing
            markdown_text = clean_ocr_duplicates(markdown_text)
            
            pages.append(PageContent(
                page_num=printed if printed is not None else physical,
                text=markdown_text,
                file_path=str(path),
                word_boxes=[],
            ))
            if progress_cb and (i + 1) % 50 == 0:
                progress_cb(i + 1, total)
        doc.close()
        if progress_cb:
            progress_cb(total, total)
    except Exception:
        pass

    if pages:
        return pages

    # Strategy 2: pdfplumber fallback
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            total = len(pdf.pages)
            limit = min(total, max_pages) if max_pages is not None else total
            for idx in range(limit):
                page = pdf.pages[idx]
                i = idx + 1
                text = page.extract_text() or ""
                if text.strip():
                    import unicodedata
                    text = unicodedata.normalize('NFC', text)
                    text = clean_ocr_duplicates(text)
                    pages.append(PageContent(
                        page_num=i,
                        text=text,
                        file_path=str(path),
                        word_boxes=[],
                    ))
                if progress_cb and i % 50 == 0:
                    progress_cb(i, total)
            if progress_cb:
                progress_cb(total, total)
    except Exception:
        pass

    if pages:
        return pages

    raise ValueError(
        "Không đọc được nội dung từ file PDF này. \n"
        "File có thể là bản scan (chỉ gồm ảnh, không có text). \n"
        "Vui lòng dùng phần mềm OCR để chuyển đổi sang PDF có text trước."
    )
