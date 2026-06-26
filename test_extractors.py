import os
import fitz
import pdfplumber
from pdfminer.high_level import extract_text as pdfminer_extract_text
from core.document_processor.pdf_reader import read_pdf

pdf_path = "c:/Users/LUAN/Desktop/Local_Study_RAG_Agent/subjects/dsa/documents/Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org).pdf"
out_dir = "artifacts/extraction_test"
os.makedirs(out_dir, exist_ok=True)

start_page = 20 # 0-indexed is 19, let's just do page indices 20, 21, 22, 23, 24
pages_to_test = [20, 21, 22, 23, 24]

# 1. Current Extractor
print("Running Current Extractor...")
# read_pdf reads all pages, so we'll just read and then filter
pages_data = read_pdf(pdf_path, max_pages=30)
current_texts = {}
for p in pages_data:
    # pdf_reader.py tries to extract printed page number. We might just rely on index.
    current_texts[p.page_num] = p.text

for i, page_idx in enumerate(pages_to_test):
    with open(f"{out_dir}/page_{page_idx}_current.txt", "w", encoding="utf-8") as f:
        # read_pdf might renumber pages. Let's just use the physical index from the list if possible.
        # But read_pdf returns a list.
        if i + 20 < len(pages_data):
            f.write(pages_data[i + 20].text)

# 2. PyMuPDF (raw)
print("Running PyMuPDF...")
doc = fitz.open(pdf_path)
for page_idx in pages_to_test:
    text = doc[page_idx].get_text("text")
    with open(f"{out_dir}/page_{page_idx}_pymupdf.txt", "w", encoding="utf-8") as f:
        f.write(text)
doc.close()

# 3. pdfplumber (raw)
print("Running pdfplumber...")
with pdfplumber.open(pdf_path) as pdf:
    for page_idx in pages_to_test:
        text = pdf.pages[page_idx].extract_text() or ""
        with open(f"{out_dir}/page_{page_idx}_pdfplumber.txt", "w", encoding="utf-8") as f:
            f.write(text)

# 4. pdfminer.six (raw)
print("Running pdfminer.six...")
for page_idx in pages_to_test:
    text = pdfminer_extract_text(pdf_path, page_numbers=[page_idx])
    with open(f"{out_dir}/page_{page_idx}_pdfminer.txt", "w", encoding="utf-8") as f:
        f.write(text)

print("Done extraction tests.")
