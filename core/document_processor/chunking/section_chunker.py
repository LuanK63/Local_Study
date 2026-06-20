from pathlib import Path
from core.document_processor.chunker import Chunk, ParentChunk, PageContent
from core.document_processor.chunking.base_chunker import BaseChunker
from langchain_text_splitters import MarkdownHeaderTextSplitter

class SectionChunker(BaseChunker):
    """
    Section-aware chunker. Splits documents by Markdown headers.
    Each section is treated as a single flat chunk (parent == child).
    """
    def __init__(self):
        pass

    def split_documents(self, pages: list[PageContent]) -> list[ParentChunk]:
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False  # Keep headers in the content
        )

        all_parents: list[ParentChunk] = []
        global_parent_idx = 0
        global_child_idx = 0

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            doc_name = Path(page.file_path).stem
            parent_docs = header_splitter.split_text(text)

            for p_doc in parent_docs:
                split_text = p_doc.page_content.strip()
                if not split_text:
                    continue

                parent_id = f"{doc_name}_p{page.page_num}_parent{global_parent_idx}"
                global_parent_idx += 1

                # Create the corresponding child containing the entire section
                child = Chunk(
                    text=split_text,
                    file_path=page.file_path,
                    page_num=page.page_num,
                    chunk_idx=global_child_idx,
                    doc_name=doc_name,
                    parent_id=parent_id
                )
                child.headers = p_doc.metadata.copy()
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
