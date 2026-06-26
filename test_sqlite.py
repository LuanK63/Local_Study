import sqlite3
c = sqlite3.connect('data/study_agent.db')
c.row_factory = sqlite3.Row
row = c.execute("SELECT parent_text FROM parent_chunks WHERE subject_id='dsa' AND file_path LIKE '%Hoàng%' LIMIT 1").fetchone()
with open("artifacts/extraction_test/test_sqlite_utf8.txt", "w", encoding="utf-8") as f:
    f.write(row["parent_text"])
