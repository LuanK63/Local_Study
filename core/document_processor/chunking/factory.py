"""
core/document_processor/chunking/factory.py
============================================
Factory function tao chunker theo ten chien luoc.
Ho tro các chien luoc: fixed, sentence, recursive, token, semantic, parent_child, section.
"""
from utils.config import get_config
from core.document_processor.chunking.base_chunker import BaseChunker
from core.document_processor.chunking.fixed_chunker import FixedChunker
from core.document_processor.chunking.sentence_chunker import SentenceChunker
from core.document_processor.chunking.recursive_chunker import RecursiveChunker
from core.document_processor.chunking.token_chunker import TokenChunker
from core.document_processor.chunking.semantic_chunker import SemanticChunker
from core.document_processor.chunking.parent_child_chunker import ParentChildChunker
from core.document_processor.chunking.section_chunker import SectionChunker


def get_chunker(
    strategy_name: str = None,
    chunk_size: int = None,
    chunk_overlap: int = None,
    parent_size: int = None,
) -> BaseChunker:
    cfg = get_config().get("retrieval", {})
    
    if strategy_name is None:
        strategy_name = cfg.get("chunking_strategy", "parent_child")
    strategy_name = strategy_name.lower().strip()

    # Đọc chunk_size và chunk_overlap từ config nếu không được truyền vào
    if chunk_size is None:
        chunk_size = cfg.get("chunk_size")
    if chunk_overlap is None:
        chunk_overlap = cfg.get("chunk_overlap")

    if strategy_name == "fixed":
        return FixedChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_unit=cfg.get("length_unit")
        )
    elif strategy_name == "sentence":
        return SentenceChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            sentence_count=cfg.get("sentence_count"),
            overlap_sentences=cfg.get("overlap_sentences")
        )
    elif strategy_name == "recursive":
        return RecursiveChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_unit=cfg.get("length_unit")
        )
    elif strategy_name == "token":
        return TokenChunker(
            chunk_size=chunk_size,   # ← giờ đọc được 128 hoặc 256
            chunk_overlap=chunk_overlap
        )
    elif strategy_name == "semantic":
        return SemanticChunker(
            target_chunk_tokens=chunk_size  # ← đọc được 300 hoặc 800
        )
    elif strategy_name == "parent_child":
        return ParentChildChunker(
            parent_size=parent_size,
            child_size=chunk_size,
            child_overlap=chunk_overlap,
        )
    elif strategy_name == "section":
        return SectionChunker()
    else:
        raise ValueError(
            f"Unknown chunking strategy: '{strategy_name}'. "
            f"Supported: fixed, sentence, recursive, token, semantic, parent_child, section"
        )
