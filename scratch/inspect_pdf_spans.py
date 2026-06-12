"""
scratch/inspect_pdf_spans.py
Inspect PyMuPDF blocks and spans on Page 1 and Page 47 of Lê Minh Hoàng book.
"""
import sys
import fitz

if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def main():
    pdf_path = "subjects/dsa/documents/Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org).pdf"
    doc = fitz.open(pdf_path)
    
    # Let's inspect Page 1 (index 0) and Page 47 (index 46)
    for page_idx in [0, 46]:
        page = doc[page_idx]
        print(f"\n================ INSPECTING PAGE INDEX {page_idx} ================")
        blocks = page.get_text("dict")["blocks"]
        for b_idx, block in enumerate(blocks[:6]):
            if "lines" not in block:
                continue
            print(f"Block {b_idx}:")
            for l_idx, line in enumerate(block["lines"]):
                spans_info = []
                for s_idx, span in enumerate(line["spans"]):
                    spans_info.append(f"'{span['text']}' (size={span['size']:.1f}, bbox={[round(x, 1) for x in span['bbox']]})")
                print(f"  Line {l_idx}: {' | '.join(spans_info)}")
                
    doc.close()

if __name__ == "__main__":
    main()
