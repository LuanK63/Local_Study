from core.document_processor.pdf_reader import read_pdf
from core.document_processor.chunker import chunk_pages

pdf_path = 'subjects/dsa/documents/Introduction to Algorithms 4th.Leiserson.Stein.Rivest.Cormen.MIT.Press.pdf'
print("Reading PDF...")
pages = read_pdf(pdf_path)
print(f"Pages extracted: {len(pages)}")
if pages:
    print(f"First page (num={pages[0].page_num}): {pages[0].text[:120]}")

chunks = chunk_pages(pages)
print(f"\nTotal chunks: {len(chunks)}")
if chunks:
    print(f"First chunk: {chunks[0].text[:120]}")
