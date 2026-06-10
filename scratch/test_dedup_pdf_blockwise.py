"""
scratch/test_dedup_pdf_blockwise.py
Test the block-wide span deduplication algorithm on Page 1 and Page 47 of the PDF.
"""
import sys
import fitz
import re

if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def extract_page_clean(page):
    try:
        blocks = page.get_text("dict")["blocks"]
    except Exception:
        return page.get_text("text")
        
    page_lines = []
    ch_pattern = re.compile(r'^(chương\s+\d+|chương\s+[ivxlcdm]+)\b', re.IGNORECASE)
    sec_pattern = re.compile(r'^\d+(\.\d+){1,3}\b')
    
    for block in blocks:
        if "lines" not in block:
            continue
            
        # 1. Collect all spans in the block
        all_spans = []
        for line in block["lines"]:
            for span in line["spans"]:
                all_spans.append(span)
                
        # 2. Identify duplicate spans at block level
        dup_spans = set()
        for i, span in enumerate(all_spans):
            text = span["text"].strip()
            if not text:
                continue
            bbox = span["bbox"]
            
            for j in range(i):
                prev_span = all_spans[j]
                # If the previous span is already classified as a duplicate, skip it
                if id(prev_span) in dup_spans:
                    continue
                if prev_span["text"].strip() == text:
                    prev_bbox = prev_span["bbox"]
                    dist_x = abs(prev_bbox[0] - bbox[0])
                    dist_y = abs(prev_bbox[1] - bbox[1])
                    if dist_x < 5.0 and dist_y < 5.0:
                        dup_spans.add(id(span))
                        break
                        
        block_text_parts = []
        is_heading = False
        heading_level = 0
        
        for line in block["lines"]:
            line_text_parts = []
            for span in line["spans"]:
                if id(span) in dup_spans:
                    continue
                text = span["text"].strip()
                if not text:
                    continue
                size = span["size"]
                flags = span["flags"]
                is_bold = bool(flags & 2)
                
                if size >= 15.5:
                    is_heading = True
                    heading_level = max(heading_level, 1)
                elif size >= 12.5 and is_bold:
                    is_heading = True
                    heading_level = max(heading_level, 2)
                elif size >= 11.0 and is_bold:
                    is_heading = True
                    heading_level = max(heading_level, 3)
                
                line_text_parts.append(span["text"])
            
            if line_text_parts:
                line_text = "".join(line_text_parts).strip()
                if line_text:
                    block_text_parts.append(line_text)
                    
        if not block_text_parts:
            continue
            
        block_content = " ".join(block_text_parts).strip()
        
        if not is_heading:
            if ch_pattern.match(block_content):
                is_heading = True
                heading_level = 1
            elif sec_pattern.match(block_content):
                dots = block_content.split()[0].count(".")
                if dots == 1:
                    is_heading = True
                    heading_level = 2
                elif dots >= 2:
                    is_heading = True
                    heading_level = 3
                    
        if is_heading and heading_level > 0:
            hashes = "#" * heading_level
            clean_text = block_content.lstrip("#").strip()
            page_lines.append(f"\n{hashes} {clean_text}\n")
        else:
            page_lines.append(block_content)
            
    return "\n".join(page_lines).strip()

def main():
    pdf_path = "subjects/dsa/documents/Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org).pdf"
    doc = fitz.open(pdf_path)
    
    for page_idx in [0, 46]:
        page = doc[page_idx]
        text = extract_page_clean(page)
        print(f"\n--- CLEANED TEXT FOR PAGE INDEX {page_idx} ---")
        print(text[:400])
        print("="*60)
        
    doc.close()

if __name__ == "__main__":
    main()
