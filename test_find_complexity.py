import sqlite3

c = sqlite3.connect('data/study_agent.db')
c.row_factory = sqlite3.Row
rows = c.execute("SELECT * FROM parent_chunks WHERE subject_id='dsa'").fetchall()

for row in rows:
    text = row["parent_text"]
    if "Xét về độ phức tạp tính toán" in text:
        print("FOUND ON PAGE:", row["page_num"])
        print("PARENT ID:", row["parent_id"])
        print("TEXT:", text[:200])
