import fitz
from core.document_processor.pdf_reader import _extract_page_as_markdown, clean_ocr_duplicates
from core.document_processor.pdf_reader import PageContent
from core.document_processor.chunking.factory import get_chunker
from utils.config import get_config
import unicodedata

pdf_path = "c:/Users/LUAN/Desktop/Local_Study_RAG_Agent/subjects/dsa/documents/Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org).pdf"

doc = fitz.open(pdf_path)
page = doc[260]
text = _extract_page_as_markdown(page)
text = unicodedata.normalize('NFC', text)
text = clean_ocr_duplicates(text)

pages = [
    PageContent(
        page_num=247,
        text=text,
        file_path=pdf_path,
        word_boxes=[]
    )
]

get_config()["chunking"] = {
    "strategy": "fixed",
    "chunk_size": 256,
    "chunk_overlap": 50,
    "hierarchical": True
}

chunker = get_chunker()
parent_chunks = chunker.split_documents(pages)

for p in parent_chunks:
    for c in p.children:
        print(f"CHUNK: {c.text}")
doc.close()
