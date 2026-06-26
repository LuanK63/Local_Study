import logging
from pathlib import Path
from core.document_processor.chunker import Chunk, ParentChunk, PageContent
from core.document_processor.chunking.base_chunker import BaseChunker
from utils.config import get_config
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

class SemanticChunker(BaseChunker):
    """
    Heuristic Semantic Chunker.
    Splits text by paragraph boundaries (`\n\n`) and groups them up to a target token limit.
    Purely heuristic, runs entirely on CPU with zero embedding/Ollama calls.
    """
    def __init__(self, target_chunk_tokens: int = None):
        cfg = get_config().get("retrieval", {})
        self.target_chunk_tokens = target_chunk_tokens if target_chunk_tokens is not None else cfg.get("fixed_chunk_size", 300)
        self.max_chunk_tokens = self.target_chunk_tokens * 2

    def split_documents(self, pages: list[PageContent]) -> list[ParentChunk]:
        all_parents: list[ParentChunk] = []
        global_parent_idx = 0
        global_child_idx = 0

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            doc_name = Path(page.file_path).stem
            paragraphs = text.split("\n\n")
            
            current_paragraphs: list[str] = []
            current_tokens = 0
            
            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue
                
                p_tokens = self.estimate_token_length(p)
                
                # If a single paragraph is too large, split it recursively
                if p_tokens > self.max_chunk_tokens:
                    if current_paragraphs:
                        global_parent_idx, global_child_idx = self._flush(
                            "\n\n".join(current_paragraphs), page, doc_name,
                            all_parents, global_parent_idx, global_child_idx
                        )
                        current_paragraphs = []
                        current_tokens = 0
                    
                    global_parent_idx, global_child_idx = self._flush_long(
                        p, page, doc_name, all_parents, global_parent_idx, global_child_idx
                    )
                    continue
                
                # If adding this paragraph exceeds the target, flush the current group
                if current_tokens + p_tokens > self.target_chunk_tokens and current_paragraphs:
                    global_parent_idx, global_child_idx = self._flush(
                        "\n\n".join(current_paragraphs), page, doc_name,
                        all_parents, global_parent_idx, global_child_idx
                    )
                    current_paragraphs = []
                    current_tokens = 0
                
                current_paragraphs.append(p)
                current_tokens += p_tokens
            
            # Flush the remaining paragraphs for the page
            if current_paragraphs:
                global_parent_idx, global_child_idx = self._flush(
                    "\n\n".join(current_paragraphs), page, doc_name,
                    all_parents, global_parent_idx, global_child_idx
                )

        return all_parents

    def _flush(self, text: str, page: PageContent, doc_name: str, 
               all_parents: list, global_parent_idx: int, global_child_idx: int):
        text = text.strip()
        if not text:
            return global_parent_idx, global_child_idx

        parent_id = f"{doc_name}_p{page.page_num}_parent{global_parent_idx}"
        global_parent_idx += 1

        child = Chunk(
            text=text,
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
            text=text,
            file_path=page.file_path,
            page_num=page.page_num,
            doc_name=doc_name,
            children=[child]
        )
        all_parents.append(parent)
        return global_parent_idx, global_child_idx

    def _flush_long(self, text: str, page: PageContent, doc_name: str, 
                    all_parents: list, global_parent_idx: int, global_child_idx: int):
        """Fallback for extra long paragraphs using RecursiveCharacterTextSplitter."""
        try:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.target_chunk_tokens,
                chunk_overlap=0,
                length_function=self.estimate_token_length
            )
            splits = splitter.split_text(text)
        except Exception as e:
            logger.warning(f"[SemanticChunker] Fallback splitter failed: {e}. Coercing split.")
            splits = [text[:len(text)//2], text[len(text)//2:]]

        for split_text in splits:
            global_parent_idx, global_child_idx = self._flush(
                split_text, page, doc_name, all_parents, global_parent_idx, global_child_idx
            )
        return global_parent_idx, global_child_idx
