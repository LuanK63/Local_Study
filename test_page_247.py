import fitz

pdf_path = "c:/Users/LUAN/Desktop/Local_Study_RAG_Agent/subjects/dsa/documents/Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org).pdf"

doc = fitz.open(pdf_path)
with open("artifacts/extraction_test/page_247.txt", "w", encoding="utf-8") as f:
    f.write("--- Page 246 ---\n")
    f.write(doc[246].get_text("text")[:500])
    f.write("\n--- Page 247 ---\n")
    f.write(doc[247].get_text("text")[:500])
    f.write("\n--- Page 289 ---\n")
    f.write(doc[289].get_text("text")[:500])
doc.close()
