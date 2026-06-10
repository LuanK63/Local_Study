"""
scratch/inspect_book_stack_2.py
Print chapters on Stack (pages 76 to 80) to check if the definition exists.
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
        SELECT page_num, parent_id, parent_text 
        FROM parent_chunks 
        WHERE page_num BETWEEN 75 AND 81
        ORDER BY page_num ASC, parent_id ASC
    """)
    rows = cursor.fetchall()
    print(f"Total matching chunks between page 75 and 81: {len(rows)}")
    
    for r in rows:
        print(f"\nPage {r['page_num']} | ParentID={r['parent_id']}")
        print(f"Text: {r['parent_text'].strip()[:400]}...")
        print("-" * 80)
        
    conn.close()

if __name__ == "__main__":
    main()
