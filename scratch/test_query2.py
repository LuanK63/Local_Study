import sqlite3
import sys

if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_query():
    conn = sqlite3.connect('data/study_agent.db')
    cur = conn.cursor()
    cur.execute("SELECT parent_text FROM parent_chunks WHERE page_num = 82")
    rows = cur.fetchall()
    print(f"Page 82 Text:")
    for r in rows:
        print(r[0])
    conn.close()

if __name__ == '__main__':
    test_query()
