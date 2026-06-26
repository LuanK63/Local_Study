from core.document_processor.chunking.recursive_chunker import RecursiveChunker

class TokenChunker(RecursiveChunker):
    """
    Token-based chunker. Inherits from RecursiveChunker but enforces token-based length.
    """
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap, length_unit="token")
