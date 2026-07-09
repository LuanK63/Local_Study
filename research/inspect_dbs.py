import sqlite3
import os
import sys

# Windows Unicode stdout fix
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

print('=== KIỂM TRA SQLITE: study_agent.db ===')
db_path = 'data/study_agent.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cur.fetchall()]
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            print(f'Table {table:<20}: {count} dòng')
            
            # Nếu là parent_chunks, liệt kê thêm các subject_id có trong đó
            if table == "parent_chunks":
                cur.execute("SELECT DISTINCT subject_id, COUNT(*) FROM parent_chunks GROUP BY subject_id;")
                subjects = cur.fetchall()
                if subjects:
                    print(" Chi tiết các môn học (subject_id) đang lưu:")
                    for sub, cnt in subjects:
                        print(f" - {sub}: {cnt} chunks")
                else:
                    print(" -> Bảng trống")
    except Exception as e:
        print('Lỗi:', e)
    finally:
        conn.close()
else:
    print('Không tìm thấy file study_agent.db')

print('\n=== KIỂM TRA SQLITE: benchmark_logs.db ===')
bench_db = 'data/benchmark_logs.db'
if os.path.exists(bench_db):
    conn = sqlite3.connect(bench_db)
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cur.fetchall()]
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            print(f'Table {table:<20}: {count} dòng')
    except Exception as e:
        print('Lỗi:', e)
    finally:
        conn.close()
else:
    print('Không tìm thấy file benchmark_logs.db')

print('\n=== KIỂM TRA CHROMADB ===')
try:
    import chromadb
    client = chromadb.PersistentClient(path='data/chroma_db')
    cols = client.list_collections()
    print(f'Tìm thấy {len(cols)} collections trong ChromaDB:')
    for col_name in cols:
        col = client.get_collection(col_name)
        print(f' - Collection: {col_name:<35} | Chunks: {col.count()}')
except Exception as e:
    print('Lỗi ChromaDB:', e)

