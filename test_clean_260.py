import fitz
from core.document_processor.pdf_reader import _extract_page_as_markdown, clean_ocr_duplicates
import unicodedata

pdf_path = "c:/Users/LUAN/Desktop/Local_Study_RAG_Agent/subjects/dsa/documents/Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org).pdf"

doc = fitz.open(pdf_path)
text = _extract_page_as_markdown(doc[260])
norm = unicodedata.normalize('NFC', text)
clean = clean_ocr_duplicates(norm)

with open("artifacts/extraction_test/page_260_clean.txt", "w", encoding="utf-8") as f:
    f.write(clean)
doc.close()
