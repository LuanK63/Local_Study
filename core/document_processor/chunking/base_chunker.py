from abc import ABC, abstractmethod
from core.document_processor.chunker import PageContent, ParentChunk

class BaseChunker(ABC):
    """
    Base class for all chunking strategies.
    Ensures a consistent interface for the ingestion pipeline.
    """
    
    @abstractmethod
    def split_documents(self, pages: list[PageContent]) -> list[ParentChunk]:
        """
        Split a list of pages into a list of ParentChunks.
        For flat chunking, each parent chunk will contain exactly one child chunk.
        """
        pass

    def estimate_token_length(self, text: str) -> int:
        """
        Estimate token count based on words (approximately 1 word = 1.3 tokens).
        """
        return int(len(text.strip().split()) * 1.3)
