from utils.config import get_config
from core.document_processor.chunking.base_chunker import BaseChunker
from core.document_processor.chunking.fixed_chunker import FixedChunker
from core.document_processor.chunking.recursive_chunker import RecursiveChunker
from core.document_processor.chunking.semantic_chunker import SemanticChunker
from core.document_processor.chunking.parent_child_chunker import ParentChildChunker
from core.document_processor.chunking.section_chunker import SectionChunker

def get_chunker(strategy_name: str = None, chunk_size: int = None, chunk_overlap: int = None, parent_size: int = None) -> BaseChunker:
    """
    Factory function to get a chunker instance based on strategy name.
    If strategy_name is not provided, it reads from the global config.
    """
    if strategy_name is None:
        cfg = get_config().get("retrieval", {})
        strategy_name = cfg.get("chunking_strategy", "parent_child")

    strategy_name = strategy_name.lower().strip()

    if strategy_name == "fixed":
        return FixedChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    elif strategy_name == "recursive":
        return RecursiveChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    elif strategy_name == "semantic":
        return SemanticChunker()
    elif strategy_name == "parent_child":
        return ParentChildChunker(parent_size=parent_size, child_size=chunk_size, child_overlap=chunk_overlap)
    elif strategy_name == "section":
        return SectionChunker()
    else:
        raise ValueError(f"Unknown chunking strategy: {strategy_name}")
