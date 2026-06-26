"""
core/document_processor/chunking/sentence_chunker.py
=====================================================
SentenceChunker -- Chia van ban theo ranh gioi cau.

Chien luoc:
  1. Tach van ban thanh tung cau don le bang cach nhan dien cac dau cau
     (. ! ?) va ki tu xuong dong.
  2. Gom nhieu cau lai thanh 1 chunk cho den khi dat target_tokens.
  3. Neu mot cau qua dai vuot max_tokens, su dung RecursiveCharacterTextSplitter
     de cat an toan.

Dac diem:
  - Khong phu thuoc NLTK (tranh them dependency nang).
  - Giu nguyen y nghia cau, khong cat giua chung.
  - Phu hop cho tai lieu ky thuat tieng Viet/Anh co cau truc cau ro rang.
"""
import re
from pathlib import Path
from core.document_processor.chunker import Chunk, ParentChunk, PageContent
from core.document_processor.chunking.base_chunker import BaseChunker
from utils.config import get_config


# Pattern nhan dien ranh gioi cau: dau . ! ? theo sau la khoang trang hoac xuong dong
_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+|(?<=\n)\s*')


def _split_into_sentences(text: str) -> list[str]:
    """
    Tach van ban thanh danh sach cau.
    Su dung regex don gian, hieu qua cho tai lieu ky thuat.
    """
    # Tach theo dau cau hoac xuong dong
    raw = re.split(r'(?<=[.!?])\s+|\n+', text)
    sentences = []
    for s in raw:
        s = s.strip()
        if s:
            sentences.append(s)
    return sentences


class SentenceChunker(BaseChunker):
    """
    Sentence-boundary chunker.
    Gom cac cau lai thanh chunk dat kich thuoc muc tieu,
    dam bao khong cat giua ranh gioi cau.
    """

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None, sentence_count: int = None, overlap_sentences: int = None):
        cfg = get_config().get("retrieval", {})
        self.target_tokens = chunk_size or cfg.get("fixed_chunk_size", 300)
        self.overlap_tokens = chunk_overlap or cfg.get("fixed_chunk_overlap", 30)
        self.max_tokens = self.target_tokens * 2
        
        self.sentence_count = sentence_count or cfg.get("sentence_count", None)
        self.overlap_sentences = overlap_sentences or cfg.get("overlap_sentences", None)
        if self.sentence_count is not None:
            if self.overlap_sentences is None:
                self.overlap_sentences = max(1, int(self.sentence_count * 0.1))

    def split_documents(self, pages: list[PageContent]) -> list[ParentChunk]:
        all_parents: list[ParentChunk] = []
        global_parent_idx = 0
        global_child_idx = 0

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            doc_name = Path(page.file_path).stem
            sentences = _split_into_sentences(text)
            if not sentences:
                continue

            if self.sentence_count is not None:
                idx = 0
                n = len(sentences)
                while idx < n:
                    chunk_sentences = sentences[idx : idx + self.sentence_count]
                    chunk_text = " ".join(chunk_sentences).strip()
                    if chunk_text:
                        global_parent_idx, global_child_idx = self._flush(
                            chunk_text, page, doc_name,
                            all_parents, global_parent_idx, global_child_idx
                        )
                    step = self.sentence_count - self.overlap_sentences
                    if step <= 0:
                        step = 1
                    idx += step
            else:
                current_sentences: list[str] = []
                current_tokens = 0

                for sentence in sentences:
                    sentence_tokens = self.estimate_token_length(sentence)

                    # Neu 1 cau don le qua lon -> cat bang RecursiveCharacterTextSplitter
                    if sentence_tokens > self.max_tokens:
                        # Flush chunk hien tai truoc
                        if current_sentences:
                            global_parent_idx, global_child_idx = self._flush(
                                " ".join(current_sentences), page, doc_name,
                                all_parents, global_parent_idx, global_child_idx
                            )
                            current_sentences = []
                            current_tokens = 0
                        # Cat cau dai bang fallback splitter
                        global_parent_idx, global_child_idx = self._flush_long(
                            sentence, page, doc_name,
                            all_parents, global_parent_idx, global_child_idx
                        )
                        continue

                    # Neu gop them se qua lon -> flush va bat dau chunk moi
                    if current_tokens + sentence_tokens > self.target_tokens and current_sentences:
                        global_parent_idx, global_child_idx = self._flush(
                            " ".join(current_sentences), page, doc_name,
                            all_parents, global_parent_idx, global_child_idx
                        )
                        # Overlap: giu lai cau cuoi cua chunk truoc neu co the
                        overlap_carry: list[str] = []
                        carry_tokens = 0
                        for prev in reversed(current_sentences):
                            pt = self.estimate_token_length(prev)
                            if carry_tokens + pt <= self.overlap_tokens:
                                overlap_carry.insert(0, prev)
                                carry_tokens += pt
                            else:
                                break
                        current_sentences = overlap_carry
                        current_tokens = carry_tokens

                    current_sentences.append(sentence)
                    current_tokens += sentence_tokens

                # Flush chunk cuoi cua trang
                if current_sentences:
                    global_parent_idx, global_child_idx = self._flush(
                        " ".join(current_sentences), page, doc_name,
                        all_parents, global_parent_idx, global_child_idx
                    )

        return all_parents

    # ------------------------------------------------------------------
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
            parent_id=parent_id,
        )
        child.headers = {}
        global_child_idx += 1

        all_parents.append(ParentChunk(
            parent_id=parent_id,
            text=text,
            file_path=page.file_path,
            page_num=page.page_num,
            doc_name=doc_name,
            children=[child],
        ))
        return global_parent_idx, global_child_idx

    def _flush_long(self, text: str, page: PageContent, doc_name: str,
                    all_parents: list, global_parent_idx: int, global_child_idx: int):
        """Fallback cho cau qua dai: dung RecursiveCharacterTextSplitter."""
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.target_tokens,
                chunk_overlap=self.overlap_tokens,
                length_function=self.estimate_token_length,
                separators=[". ", " ", ""]
            )
            splits = splitter.split_text(text)
        except Exception:
            splits = [text]

        for split_text in splits:
            global_parent_idx, global_child_idx = self._flush(
                split_text, page, doc_name,
                all_parents, global_parent_idx, global_child_idx
            )
        return global_parent_idx, global_child_idx
