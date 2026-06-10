import sqlite3
import sys

if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_query():
    conn = sqlite3.connect('data/study_agent.db')
    cur = conn.cursor()
    cur.execute("SELECT page_num, parent_text FROM parent_chunks WHERE parent_text LIKE '%Push%' OR parent_text LIKE '%Pop%'")
    rows = cur.fetchall()
    print(f"Found {len(rows)} parent chunks containing 'Push' or 'Pop':")
    for r in rows[:10]:
        print(f"Page {r[0]}: {r[1][:150]}...\n")
    conn.close()

if __name__ == '__main__':
    test_query()
