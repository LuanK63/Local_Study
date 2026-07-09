from pathlib import Path

from core.document_processor.chunker import Chunk, ParentChunk, PageContent
from core.document_processor.chunking.base_chunker import BaseChunker
from utils.config import get_config


class ParagraphChunker(BaseChunker):
    """Paragraph-based Chunker.

    Splits text by paragraph boundaries (`\\n\\n`) and groups them based on
    paragraphs_per_chunk and overlap_paragraphs.
    """

    def __init__(self, paragraphs_per_chunk: int = None, overlap_paragraphs: int = None):
        cfg = get_config().get("retrieval", {})
        self.paragraphs_per_chunk = paragraphs_per_chunk if paragraphs_per_chunk is not None else cfg.get("paragraphs_per_chunk", 1)
        self.overlap_paragraphs = overlap_paragraphs if overlap_paragraphs is not None else cfg.get("overlap_paragraphs", 0)

        # Define attributes for Ingest Logger compatibility
        self.chunk_size = self.paragraphs_per_chunk
        self.chunk_overlap = self.overlap_paragraphs
        self.length_unit = "paragraph"

    def split_documents(self, pages: list[PageContent]) -> list[ParentChunk]:
        parents = []
        parent_idx = 0
        child_idx = 0

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            doc_name = Path(page.file_path).stem
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            if not paragraphs:
                continue

            idx = 0
            n = len(paragraphs)
            while idx < n:
                chunk_paras = paragraphs[idx : idx + self.paragraphs_per_chunk]
                chunk_text = "\n\n".join(chunk_paras).strip()
                if chunk_text:
                    parent_id = f"{doc_name}_p{page.page_num}_{parent_idx}"
                    child = Chunk(
                        text=chunk_text,
                        file_path=page.file_path,
                        page_num=page.page_num,
                        chunk_idx=child_idx,
                        doc_name=doc_name,
                        parent_id=parent_id,
                    )
                    parents.append(
                        ParentChunk(
                            parent_id=parent_id,
                            text=chunk_text,
                            file_path=page.file_path,
                            page_num=page.page_num,
                            doc_name=doc_name,
                            children=[child],
                        )
                    )
                    parent_idx += 1
                    child_idx += 1

                step = self.paragraphs_per_chunk - self.overlap_paragraphs
                if step <= 0:
                    step = 1
                idx += step

        return parents
