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
    parent_id: str = ""   # ID của parent chunk chứa child này (rỗng nếu dùng flat chunking)


@dataclass
class ParentChunk:
    """
    Parent chunk (lớn) — được gửi cho LLM để sinh câu trả lời.
    Chứa danh sách các child Chunk nhỏ được embed vào vector DB.
    """
    parent_id: str         # khóa duy nhất: "{doc_name}_p{page}_parent{idx}"
    text: str              # văn bản đầy đủ gửi cho LLM
    file_path: str
    page_num: int
    doc_name: str
    children: list         # list[Chunk] — các child chunk được embed


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

def estimate_token_length(text: str) -> int:
    """
    Ước lượng số lượng tokens dựa trên số lượng từ (words).
    Tiếng Anh/Việt: 1 từ ~ 1.3 tokens.
    """
    return int(len(text.strip().split()) * 1.3)


def chunk_pages(
    pages: list[PageContent],
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    separators: list[str] | None = None,
) -> list[Chunk]:
    """
    Chia nội dung từng trang bằng RecursiveCharacterTextSplitter (flat mode) theo số lượng từ/token.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=estimate_token_length,
        separators=separators or ["\n\n", "\n", ". ", " ", ""]
    )

    all_chunks: list[Chunk] = []
    global_idx = 0

    for page in pages:
        text = page.text.strip()
        if not text:
            continue

        doc_name = Path(page.file_path).stem
        splits = splitter.split_text(text)

        for split_text in splits:
            split_text = split_text.strip()
            if not split_text:
                continue
            all_chunks.append(Chunk(
                text=split_text,
                file_path=page.file_path,
                page_num=page.page_num,
                chunk_idx=global_idx,
                doc_name=doc_name,
            ))
            global_idx += 1

    return all_chunks


def chunk_pages_hierarchical(
    pages: list[PageContent],
    parent_size: int = 1200,
    child_size: int = 300,
    child_overlap: int = 30,
    separators: list[str] | None = None,
) -> list[ParentChunk]:
    """
    Chia tài liệu theo 2 tầng kết hợp giữa:
    1. MarkdownHeaderTextSplitter (Tách theo cấu trúc tiêu đề Markdown - làm Parent Chunks)
    2. RecursiveCharacterTextSplitter (Tách nhỏ các đoạn lớn thành các Child Chunks có gối đầu/overlap)

    Đảm bảo:
    - Chạy theo từng trang để bảo toàn chính xác page_num của PDF.
    - Kế thừa toàn bộ tiêu đề (metadata) từ parent sang child.
    - Sử dụng bộ đếm tokens thay vì số lượng ký tự.
    """
    from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False  # Giữ lại headers trong nội dung văn bản để không mất ngữ cảnh
    )
    
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_size,
        chunk_overlap=child_overlap,
        length_function=estimate_token_length,
        separators=separators or ["\n\n", "\n", ". ", " ", ""]
    )

    all_parents: list[ParentChunk] = []
    global_parent_idx = 0
    global_child_idx = 0

    for page in pages:
        text = page.text.strip()
        if not text:
            continue

        doc_name = Path(page.file_path).stem

        # Bước 1: Tách theo Header cấu trúc bằng MarkdownHeaderTextSplitter (Parent Chunks)
        parent_docs = header_splitter.split_text(text)

        for p_doc in parent_docs:
            parent_text = p_doc.page_content.strip()
            if not parent_text:
                continue

            # Sử dụng global_parent_idx để đảm bảo parent_id luôn duy nhất trong tài liệu
            parent_id = f"{doc_name}_p{page.page_num}_parent{global_parent_idx}"
            global_parent_idx += 1

            # Bước 2: Cắt mỗi parent thành các child chunk nhỏ
            splits = child_splitter.split_documents([p_doc])

            children: list[Chunk] = []
            for split_doc in splits:
                child_text = split_doc.page_content.strip()
                if not child_text:
                    continue
                
                # Tạo Chunk con kế thừa metadata tiêu đề
                c = Chunk(
                    text=child_text,
                    file_path=page.file_path,
                    page_num=page.page_num,
                    chunk_idx=global_child_idx,
                    doc_name=doc_name,
                    parent_id=parent_id,
                )
                
                # Lưu thông tin tiêu đề thừa kế vào thuộc tính động để đẩy vào db/chromadb
                c.headers = split_doc.metadata.copy()
                
                children.append(c)
                global_child_idx += 1

            if children:
                all_parents.append(ParentChunk(
                    parent_id=parent_id,
                    text=parent_text,
                    file_path=page.file_path,
                    page_num=page.page_num,
                    doc_name=doc_name,
                    children=children,
                ))

    return all_parents
