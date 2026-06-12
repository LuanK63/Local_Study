"""
scratch/inspect_book_stack.py
Find pages/chunks in the Lê Minh Hoàng book that mention stack or ngăn xếp.
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
    
    # Search parent chunks containing "ngăn xếp" or "stack"
    cursor.execute("""
        SELECT page_num, parent_id, doc_name, parent_text 
        FROM parent_chunks 
        WHERE parent_text LIKE '%ngăn xếp%' 
           OR parent_text LIKE '%stack%'
           OR parent_text LIKE '%lifo%'
    """)
    rows = cursor.fetchall()
    print(f"Total matching parent chunks in SQLite: {len(rows)}")
    
    for i, r in enumerate(rows, 1):
        print(f"\n[{i}] Page={r['page_num']} | ParentID={r['parent_id']}")
        print(f"    Text: {r['parent_text'].strip()[:250]}...")
        print("-" * 80)
        
    conn.close()

if __name__ == "__main__":
    main()
