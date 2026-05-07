"""
core/document_processor/chunker.py
Split page content into overlapping chunks for embedding.
Preserves source metadata (file_path, page_num, chunk_idx).
"""
from dataclasses import dataclass
from typing import Union
from core.document_processor.pdf_reader import PageContent as PDFPage
from core.document_processor.docx_reader import PageContent as DocxPage


@dataclass
class Chunk:
    text: str
    file_path: str
    page_num: int
    chunk_idx: int
    doc_name: str          # basename without extension


PageContent = Union[PDFPage, DocxPage]


def chunk_pages(
    pages: list[PageContent],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Chunk]:
    """
    Split each page's text into overlapping word-level chunks.
    chunk_size and chunk_overlap are in words.
    """
    from pathlib import Path
    chunks = []
    for page in pages:
        words = page.text.split()
        if not words:
            continue
        doc_name = Path(page.file_path).stem
        start, idx = 0, 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            text = " ".join(words[start:end])
            chunks.append(Chunk(
                text=text,
                file_path=page.file_path,
                page_num=page.page_num,
                chunk_idx=idx,
                doc_name=doc_name,
            ))
            if end == len(words):
                break
            start += chunk_size - chunk_overlap
            idx += 1
    return chunks
