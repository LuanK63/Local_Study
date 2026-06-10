import sqlite3

conn = sqlite3.connect('data/study_agent.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print('Tables:', tables)

# Check parent_chunks table
cursor.execute("SELECT COUNT(*) FROM parent_chunks")
total = cursor.fetchone()[0]
print(f'Total parent_chunks: {total}')

if total > 0:
    cursor.execute("SELECT DISTINCT subject_id FROM parent_chunks")
    subjects = cursor.fetchall()
    print(f'Subjects: {subjects}')

    for subj in subjects:
        sid = subj[0]
        cursor.execute(f"SELECT COUNT(*) FROM parent_chunks WHERE subject_id=?", (sid,))
        print(f"  [{sid}] count: {cursor.fetchone()[0]}")

    # Sample
    cursor.execute("SELECT subject_id, doc_name, id FROM parent_chunks LIMIT 5")
    rows = cursor.fetchall()
    print('\nSample rows:')
    for row in rows:
        print(f'  {row}')

conn.close()
