import sqlite3
c = sqlite3.connect('data/study_agent.db')
print(c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='parent_chunks'").fetchone()[0])
