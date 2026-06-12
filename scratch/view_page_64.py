"""
scratch/view_page_64.py
Print parent chunks of Page 64 to inspect their text content and OCR quality.
"""
import sys
import sqlite3

if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def main():
    conn = sqlite3.connect('data/study_agent.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT parent_id, page_num, parent_text 
        FROM parent_chunks 
        WHERE page_num = 64
    """)
    rows = cursor.fetchall()
    print(f"Total chunks on page 64: {len(rows)}")
    for r in rows:
        print(f"\nParentID={r['parent_id']}")
        print(f"Text:\n{r['parent_text']}")
        print("="*80)
        
    conn.close()

if __name__ == "__main__":
    main()
