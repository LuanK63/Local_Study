"""
core/document_processor/chunking/factory.py
============================================
Factory function tao chunker theo ten chien luoc.
Ho tro 5 chien luoc: fixed, sentence, recursive, semantic, parent_child.
"""
from utils.config import get_config
from core.document_processor.chunking.base_chunker import BaseChunker
from core.document_processor.chunking.fixed_chunker import FixedChunker
from core.document_processor.chunking.sentence_chunker import SentenceChunker
from core.document_processor.chunking.recursive_chunker import RecursiveChunker
from core.document_processor.chunking.semantic_chunker import SemanticChunker
from core.document_processor.chunking.parent_child_chunker import ParentChildChunker
from core.document_processor.chunking.section_chunker import SectionChunker


def get_chunker(
    strategy_name: str = None,
    chunk_size: int = None,
    chunk_overlap: int = None,
    parent_size: int = None,
) -> BaseChunker:
    """
    Factory function tao mot instance chunker dua tren ten chien luoc.

    Args:
        strategy_name : Ten chien luoc (fixed | sentence | recursive | semantic |
                        parent_child | section). Neu None, doc tu global_config.yaml.
        chunk_size    : Kich thuoc chunk (tokens). Ghi de gia tri trong config.
        chunk_overlap : Do goi dau (tokens). Ghi de gia tri trong config.
        parent_size   : Kich thuoc parent chunk (chi dung voi parent_child).

    Returns:
        Instance cua BaseChunker tuong ung.
    """
    if strategy_name is None:
        cfg = get_config().get("retrieval", {})
        strategy_name = cfg.get("chunking_strategy", "parent_child")

    strategy_name = strategy_name.lower().strip()

    if strategy_name == "fixed":
        return FixedChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    elif strategy_name == "sentence":
        return SentenceChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    elif strategy_name == "recursive":
        return RecursiveChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    elif strategy_name == "semantic":
        return SemanticChunker(target_chunk_tokens=chunk_size)
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
            f"Supported: fixed, sentence, recursive, semantic, parent_child, section"
        )
