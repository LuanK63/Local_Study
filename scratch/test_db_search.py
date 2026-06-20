import sqlite3

def test_search():
    conn = sqlite3.connect('data/study_agent.db')
    keywords = [
        ("danh sách", "liên kết"),
        ("sắp xếp", "nhanh"),
        ("nhị phân", "tìm kiếm"),
        ("độ phức tạp", "Big-O")
    ]
    
    with open('scratch/search_results.txt', 'a', encoding='utf-8') as f:
        for kw1, kw2 in keywords:
            f.write(f"\n--- Searching for: {kw1} & {kw2} ---\n")
            query = f"SELECT doc_name, page_num, SUBSTR(parent_text, 1, 100) FROM parent_chunks WHERE parent_text LIKE '%{kw1}%' AND parent_text LIKE '%{kw2}%' LIMIT 3"
            rows = conn.execute(query).fetchall()
            for r in rows:
                f.write(f"Doc: {r[0]} | Page: {r[1]} | Text: {r[2].replace('\n', ' ')}\n")
    conn.close()

if __name__ == '__main__':
    test_search()
