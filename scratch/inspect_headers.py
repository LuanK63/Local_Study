"""
scratch/inspect_headers.py
List all section headers in the SQLite DB to find chapters/sections.
"""
import sys
import sqlite3

# Reconfigure stdout to use UTF-8
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
        WHERE parent_text LIKE '%###%'
        ORDER BY page_num ASC, parent_id ASC
    """)
    rows = cursor.fetchall()
    print(f"Total parent chunks with headers: {len(rows)}")
    
    for r in rows:
        lines = r['parent_text'].splitlines()
        for line in lines:
            if line.startswith('###'):
                print(f"Page {r['page_num']} | {line}")
                
    conn.close()

if __name__ == "__main__":
    main()
