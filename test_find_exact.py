import sqlite3
c = sqlite3.connect('data/study_agent.db')
c.row_factory = sqlite3.Row
rows = c.execute("SELECT parent_text FROM parent_chunks WHERE subject_id='dsa'").fetchall()

found = False
for row in rows:
    text = row["parent_text"]
    if "không âm" in text and "Dijkstra" in text:
        print("FOUND SOMEWHERE!")
        print(text[:200])
        found = True

if not found:
    print("NOT FOUND AT ALL IN ANY CHUNK!")
