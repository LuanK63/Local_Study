"""
core/document_processor/chunking/base_chunker.py
=================================================
BaseChunker — Interface chuẩn hoa cho tat ca chien luoc chunking.

Cung cap hai interface:
  - split_documents() : Interface goc, tra ve list[ParentChunk] dung boi ingest pipeline.
  - chunk()           : Interface moi (Benchmark), tra ve list[BenchmarkChunk] phang
                        dong nhat giua moi chien luoc de Benchmark Framework so sanh cong bang.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from core.document_processor.chunker import PageContent, ParentChunk


# -- Benchmark Chunk Schema ----------------------------------------------------
@dataclass
class BenchmarkChunk:
    """
    Don vi chunk chuan hoa dung trong Benchmark Framework.
    Tat ca chunker phai tra ve list[BenchmarkChunk] qua method chunk().

    Fields:
        text      : Noi dung van ban cua chunk.
        chunk_id  : ID duy nhat cua chunk.
        parent_id : ID cua parent chunk (None neu flat chunking).
        metadata  : {doc_name: str, file_path: str, page_num: int | None}
    """
    text: str
    chunk_id: str
    parent_id: str | None
    metadata: dict = field(default_factory=dict)


# -- Base Interface ------------------------------------------------------------
class BaseChunker(ABC):
    """
    Base class cho tat ca chien luoc chunking.
    Dam bao interface nhat quan cho ca ingest pipeline va benchmark framework.
    """

    @abstractmethod
    def split_documents(self, pages: list[PageContent]) -> list[ParentChunk]:
        """
        Interface goc (Ingest Pipeline).
        Chia danh sach pages thanh list[ParentChunk] co cau truc phan cap.
        Voi flat chunking (fixed/recursive/semantic/sentence),
        moi ParentChunk chua dung 1 child.
        """
        pass

    def chunk(self, pages: list[PageContent]) -> list[BenchmarkChunk]:
        """
        Interface Benchmark Framework.
        Tra ve danh sach BenchmarkChunk phang (flat) -- dung de so sanh cong bang
        giua tat ca chien luoc. Mac dinh: adapter tu split_documents().
        ParentChildChunker override method nay de tra ve cac child chunk.
        """
        parent_chunks = self.split_documents(pages)
        result: list[BenchmarkChunk] = []
        for pc in parent_chunks:
            for child in pc.children:
                result.append(BenchmarkChunk(
                    text=child.text,
                    chunk_id=f"{child.doc_name}_c{child.chunk_idx}",
                    parent_id=child.parent_id or None,
                    metadata={
                        "doc_name": child.doc_name,
                        "file_path": child.file_path,
                        "page_num": child.page_num,
                    }
                ))
        return result

    def estimate_token_length(self, text: str) -> int:
        """
        Uoc luong so token dua tren so tu (1 word ~ 1.3 tokens).
        """
        return int(len(text.strip().split()) * 1.3)
