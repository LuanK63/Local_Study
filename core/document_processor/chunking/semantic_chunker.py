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
    Replaces embedding-based cosine distance with structural text splitting (paragraphs).
    Fast, deterministic, and highly efficient for technical PDFs.
    """
    def __init__(self, target_chunk_tokens: int = None):
        # threshold_factor is ignored in heuristic mode, kept for factory backward compatibility.
        cfg = get_config().get("retrieval", {})
        self.target_chunk_tokens = target_chunk_tokens if target_chunk_tokens is not None else cfg.get("recursive_chunk_size", 400)
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
            # 1. Tách văn bản theo Paragraph (ranh giới tự nhiên)
            paragraphs = text.split("\n\n")
            
            current_chunk_text = ""
            
            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue
                
                # Tính trước độ lớn nếu gộp
                preview_text = f"{current_chunk_text}\n\n{p}" if current_chunk_text else p
                
                # 2. Xử lý Gom Đoạn
                if self.estimate_token_length(preview_text) > self.target_chunk_tokens:
                    # Đã đạt target, flush chunk hiện tại
                    if current_chunk_text:
                        global_parent_idx, global_child_idx = self._flush_chunk(
                            current_chunk_text, page, doc_name, all_parents, global_parent_idx, global_child_idx
                        )
                    current_chunk_text = p
                else:
                    # Gộp tiếp
                    current_chunk_text = preview_text
            
            # Flush chunk cuối của trang
            if current_chunk_text:
                global_parent_idx, global_child_idx = self._flush_chunk(
                    current_chunk_text, page, doc_name, all_parents, global_parent_idx, global_child_idx
                )

        return all_parents

    def _flush_chunk(self, text: str, page: PageContent, doc_name: str, 
                     all_parents: list, global_parent_idx: int, global_child_idx: int):
        # 3. Fallback An Toàn (Chống chunk vỡ giới hạn max)
        if self.estimate_token_length(text) > self.max_chunk_tokens:
            try:
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.target_chunk_tokens,
                    chunk_overlap=0,
                    length_function=self.estimate_token_length
                )
                splits = splitter.split_text(text)
            except Exception as e:
                # Nếu import lỗi hoặc có ngoại lệ, cố gắng chẻ thô để tránh crash
                logger.warning(f"[SemanticChunker] Fallback failed: {e}. Coercing split.")
                splits = [text[:len(text)//2], text[len(text)//2:]]
        else:
            splits = [text]
            
        return self._create_parent_chunks(splits, page, doc_name, all_parents, global_parent_idx, global_child_idx)

    def _create_parent_chunks(self, splits: list[str], page: PageContent, doc_name: str, 
                              all_parents: list, global_parent_idx: int, global_child_idx: int):
        for split_text in splits:
            split_text = split_text.strip()
            if not split_text:
                continue

            parent_id = f"{doc_name}_p{page.page_num}_parent{global_parent_idx}"
            global_parent_idx += 1

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
            
        return global_parent_idx, global_child_idx
