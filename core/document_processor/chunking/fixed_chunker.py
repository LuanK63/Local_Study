from pathlib import Path
from core.document_processor.chunker import Chunk, ParentChunk, PageContent
from core.document_processor.chunking.base_chunker import BaseChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.config import get_config

class FixedChunker(BaseChunker):
    """
    Fixed-size chunker. Splits text by words up to a target token size.
    Each chunk behaves as both parent and child (flat chunking).
    """
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None, length_unit: str = None):
        cfg = get_config().get("retrieval", {})
        self.chunk_size = chunk_size or cfg.get("fixed_chunk_size", 300)
        self.chunk_overlap = chunk_overlap or cfg.get("fixed_chunk_overlap", 30)
        self.length_unit = length_unit or cfg.get("length_unit", "char")

    def split_documents(self, pages: list[PageContent]) -> list[ParentChunk]:
        length_fn = self.estimate_token_length if self.length_unit == "token" else len
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=length_fn,
            separators=[" "]
        )

        all_parents: list[ParentChunk] = []
        global_parent_idx = 0
        global_child_idx = 0

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

                parent_id = f"{doc_name}_p{page.page_num}_parent{global_parent_idx}"
                global_parent_idx += 1

                # Create the corresponding child
                child = Chunk(
                    text=split_text,
                    file_path=page.file_path,
                    page_num=page.page_num,
                    chunk_idx=global_child_idx,
                    doc_name=doc_name,
                    parent_id=parent_id
                )
                child.headers = {}
                global_child_idx += 1

                parent = ParentChunk(
                    parent_id=parent_id,
                    text=split_text,
                    file_path=page.file_path,
                    page_num=page.page_num,
                    doc_name=doc_name,
                    children=[child]
                )
                all_parents.append(parent)

        return all_parents
