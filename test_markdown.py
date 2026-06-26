import fitz
from core.document_processor.pdf_reader import _extract_page_as_markdown

pdf_path = "c:/Users/LUAN/Desktop/Local_Study_RAG_Agent/subjects/dsa/documents/Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org).pdf"

doc = fitz.open(pdf_path)
text = _extract_page_as_markdown(doc[260])
with open("artifacts/extraction_test/page_260_markdown.txt", "w", encoding="utf-8") as f:
    f.write(text)
doc.close()
