import chromadb
from utils.config import get_config

db_path = get_config()["chromadb"]["path"]
client = chromadb.PersistentClient(path=db_path)
col = client.get_collection("dsa")

results = col.get(
    where={"doc_name": "Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org)"},
    limit=5
)
for doc, meta in zip(results["documents"], results["metadatas"]):
    print("-----")
    print("META:", meta)
    print("DOC:", doc)
