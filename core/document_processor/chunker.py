"""
core/document_processor/chunker.py
===================================
RecursiveCharacterTextSplitter — triển khai thuần Python,
không yêu cầu thư viện langchain.

Thuật toán:
  1. Thử tách văn bản theo separator ưu tiên cao (đoạn văn "\n\n").
  2. Nếu đoạn tách ra vẫn còn lớn hơn chunk_size → đệ quy dùng
     separator ưu tiên thấp hơn ("\n", ". ", " ", "").
  3. Gộp các đoạn nhỏ lại cho đến khi đạt chunk_size, giữ lại
     chunk_overlap ký tự cuối của chunk trước để tránh mất ngữ cảnh.

Đơn vị: ký tự (characters), nhất quán với cách LangChain tính.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Union
from pathlib import Path

from core.document_processor.pdf_reader import PageContent as PDFPage
from core.document_processor.docx_reader import PageContent as DocxPage


# ── Data types ────────────────────────────────────────────────────────────────
@dataclass
class Chunk:
    text: str
    file_path: str
    page_num: int
    chunk_idx: int
    doc_name: str          # basename without extension


PageContent = Union[PDFPage, DocxPage]


# ── RecursiveCharacterTextSplitter core ───────────────────────────────────────
_DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", " ", ""]


def _split_text_recursive(
    text: str,
    separators: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """
    Đệ quy chia text với danh sách separator theo thứ tự ưu tiên.
    Trả về list các string, mỗi string ≤ chunk_size ký tự.
    """
    if not text:
        return []

    # Chọn separator phù hợp đầu tiên (tìm thấy trong text)
    chosen_sep = ""
    remaining_seps: list[str] = []
    for i, sep in enumerate(separators):
        if sep == "" or sep in text:
            chosen_sep = sep
            remaining_seps = separators[i + 1:]
            break

    # Tách text theo separator đã chọn
    if chosen_sep:
        splits = text.split(chosen_sep)
    else:
        splits = list(text)

    good_chunks: list[str] = []   # đoạn đủ nhỏ
    big_pieces:  list[str] = []   # đoạn cần đệ quy tiếp

    for piece in splits:
        if not piece:
            continue
        if len(piece) <= chunk_size:
            good_chunks.append(piece)
        elif remaining_seps:
            # Đệ quy với separator ưu tiên thấp hơn
            sub = _split_text_recursive(piece, remaining_seps, chunk_size, chunk_overlap)
            good_chunks.extend(sub)
        else:
            # Không còn separator nào → cắt cứng
            for i in range(0, len(piece), chunk_size - chunk_overlap):
                good_chunks.append(piece[i: i + chunk_size])

    # Gộp các đoạn nhỏ lại, đảm bảo mỗi chunk ≤ chunk_size
    return _merge_splits(good_chunks, chosen_sep, chunk_size, chunk_overlap)


def _merge_splits(
    splits: list[str],
    separator: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """
    Gộp các đoạn nhỏ thành chunks đạt kích thước mục tiêu.
    Giữ lại chunk_overlap ký tự từ chunk trước để bảo toàn ngữ cảnh.
    """
    chunks: list[str] = []
    current_pieces: list[str] = []
    current_len = 0

    for piece in splits:
        piece_len = len(piece)
        join_sep = separator if current_pieces else ""
        added_len = len(join_sep) + piece_len

        if current_pieces and current_len + added_len > chunk_size:
            # Lưu chunk hiện tại
            chunk_text = separator.join(current_pieces).strip()
            if chunk_text:
                chunks.append(chunk_text)

            # Giữ lại overlap: lấy các piece cuối sao cho tổng ≤ chunk_overlap
            overlap_pieces: list[str] = []
            overlap_len = 0
            for p in reversed(current_pieces):
                if overlap_len + len(p) > chunk_overlap:
                    break
                overlap_pieces.insert(0, p)
                overlap_len += len(p)

            current_pieces = overlap_pieces
            current_len = overlap_len

        current_pieces.append(piece)
        current_len += added_len

    # Thêm chunk cuối
    if current_pieces:
        chunk_text = separator.join(current_pieces).strip()
        if chunk_text:
            chunks.append(chunk_text)

    return chunks


# ── Public API ────────────────────────────────────────────────────────────────
def chunk_pages(
    pages: list[PageContent],
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    separators: list[str] | None = None,
) -> list[Chunk]:
    """
    Chia nội dung từng trang bằng RecursiveCharacterTextSplitter.

    Args:
        pages:         Danh sách PageContent từ pdf_reader / docx_reader.
        chunk_size:    Kích thước chunk tối đa tính theo ký tự (mặc định 1000).
        chunk_overlap: Số ký tự gối nhau giữa hai chunk liên tiếp (mặc định 150).
        separators:    Danh sách separator theo thứ tự ưu tiên. Mặc định:
                       ["\n\n", "\n", ". ", "! ", "? ", " ", ""]

    Returns:
        Danh sách Chunk với đầy đủ metadata (file_path, page_num, chunk_idx).
    """
    if separators is None:
        separators = _DEFAULT_SEPARATORS

    all_chunks: list[Chunk] = []

    for page in pages:
        text = page.text.strip()
        if not text:
            continue

        doc_name = Path(page.file_path).stem
        raw_splits = _split_text_recursive(text, separators, chunk_size, chunk_overlap)

        for idx, split_text in enumerate(raw_splits):
            split_text = split_text.strip()
            if not split_text:
                continue
            all_chunks.append(Chunk(
                text=split_text,
                file_path=page.file_path,
                page_num=page.page_num,
                chunk_idx=idx,
                doc_name=doc_name,
            ))

    return all_chunks
