import fitz

pdf_path = "c:/Users/LUAN/Desktop/Local_Study_RAG_Agent/subjects/dsa/documents/Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org).pdf"

doc = fitz.open(pdf_path)
with open("artifacts/extraction_test/page_260.txt", "w", encoding="utf-8") as f:
    f.write(doc[260].get_text("text")[:500])
doc.close()
