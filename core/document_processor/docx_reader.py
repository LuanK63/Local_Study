"""
core/document_processor/docx_reader.py
Extract text from DOCX files, preserving paragraph structure.
"""
from dataclasses import dataclass
from pathlib import Path
import docx


@dataclass
class PageContent:
    page_num: int
    text: str
    file_path: str
    word_boxes: list = None   # DOCX has no pixel coords — kept for API compat


def read_docx(file_path: str | Path) -> list[PageContent]:
    """Extract paragraphs from a DOCX file. Groups into ~500-word virtual pages."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"DOCX not found: {file_path}")

    import unicodedata
    doc = docx.Document(str(path))
    paragraphs = [unicodedata.normalize('NFC', p.text.strip()) for p in doc.paragraphs if p.text.strip()]

    # Group paragraphs into virtual "pages" of ~400 words each
    pages, current, word_count, page_num = [], [], 0, 1
    for para in paragraphs:
        words = len(para.split())
        if word_count + words > 400 and current:
            pages.append(PageContent(
                page_num=page_num,
                text="\n".join(current),
                file_path=str(path),
            ))
            current, word_count, page_num = [], 0, page_num + 1
        current.append(para)
        word_count += words

    if current:
        pages.append(PageContent(
            page_num=page_num,
            text="\n".join(current),
            file_path=str(path),
        ))
    return pages
