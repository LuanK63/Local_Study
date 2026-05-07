"""
core/document_processor/pdf_reader.py
Extract text + metadata from PDF files using PyMuPDF (primary) / pdfplumber (fallback).
No page limit — suitable for large books (1000+ pages).
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Generator, Callable
import fitz  # PyMuPDF


@dataclass
class PageContent:
    page_num: int          # 1-indexed
    text: str
    file_path: str
    word_boxes: list = field(default_factory=list)


def read_pdf(
    file_path: str | Path,
    progress_cb: Callable[[int, int], None] | None = None,
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
        for i in range(total):
            page = doc[i]
            text = page.get_text("text")
            if text.strip():
                pages.append(PageContent(
                    page_num=i + 1,
                    text=text,
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
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
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
