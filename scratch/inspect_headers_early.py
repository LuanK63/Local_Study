"""
scratch/inspect_headers_early.py
List all section headers in the SQLite DB under page 82 to see if there is any stack definition chapter.
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
        SELECT page_num, parent_text 
        FROM parent_chunks 
        WHERE parent_text LIKE '%###%' AND page_num < 82
        ORDER BY page_num ASC
    """)
    rows = cursor.fetchall()
    
    for r in rows:
        lines = r['parent_text'].splitlines()
        for line in lines:
            if line.startswith('###'):
                print(f"Page {r['page_num']} | {line}")
                
    conn.close()

if __name__ == "__main__":
    main()
