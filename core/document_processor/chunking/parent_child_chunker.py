from pathlib import Path
from core.document_processor.chunker import Chunk, ParentChunk, PageContent
from core.document_processor.chunking.base_chunker import BaseChunker
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from utils.config import get_config

class ParentChildChunker(BaseChunker):
    """
    Hierarchical Parent-Child chunker.
    Splits document structurally using Markdown headers for parent chunks,
    and then recursively splits into smaller child chunks.
    """
    def __init__(self, parent_size: int = None, child_size: int = None, child_overlap: int = None):
        cfg = get_config().get("retrieval", {})
        self.parent_size = parent_size or cfg.get("parent_chunk_size", 1200)
        self.child_size = child_size or cfg.get("child_chunk_size", 300)
        self.child_overlap = child_overlap or cfg.get("child_chunk_overlap", 30)

    def split_documents(self, pages: list[PageContent]) -> list[ParentChunk]:
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False  # Retain headers in the text for context
        )
        
        child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.child_size,
            chunk_overlap=self.child_overlap,
            length_function=self.estimate_token_length,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        all_parents: list[ParentChunk] = []
        global_parent_idx = 0
        global_child_idx = 0

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            doc_name = Path(page.file_path).stem

            # Step 1: Split into Parent Chunks by Markdown headers
            parent_docs = header_splitter.split_text(text)

            for p_doc in parent_docs:
                parent_text = p_doc.page_content.strip()
                if not parent_text:
                    continue

                parent_id = f"{doc_name}_p{page.page_num}_parent{global_parent_idx}"
                global_parent_idx += 1

                # Step 2: Split parent into smaller child chunks
                splits = child_splitter.split_documents([p_doc])

                children: list[Chunk] = []
                for split_doc in splits:
                    child_text = split_doc.page_content.strip()
                    if not child_text:
                        continue
                    
                    c = Chunk(
                        text=child_text,
                        file_path=page.file_path,
                        page_num=page.page_num,
                        chunk_idx=global_child_idx,
                        doc_name=doc_name,
                        parent_id=parent_id,
                    )
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
