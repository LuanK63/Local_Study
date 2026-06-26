import sqlite3
c = sqlite3.connect('data/study_agent.db')
c.row_factory = sqlite3.Row
rows = c.execute("SELECT parent_text FROM parent_chunks WHERE subject_id='dsa' AND parent_text LIKE '%Dijkstra%'").fetchall()

for row in rows:
    text = row["parent_text"]
    # find occurrences of Dijkstra and print 100 chars before and after
    idx = text.find("Dijkstra")
    if idx != -1:
        start = max(0, idx - 100)
        end = min(len(text), idx + 100)
        print("MATCH:", text[start:end].replace('\n', ' '))
