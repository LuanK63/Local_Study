import fitz

pdf_path = "c:/Users/LUAN/Desktop/Local_Study_RAG_Agent/subjects/dsa/documents/Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org).pdf"

doc = fitz.open(pdf_path)
full_text = ""
for i in range(230, 260):
    full_text += doc[i].get_text("text")

idx = full_text.find("có trọng số không âm")
if idx != -1:
    print("FOUND: ", full_text[idx-50:idx+50].replace('\n', ' '))
else:
    print("NOT FOUND 'có trọng số không âm'")

idx2 = full_text.find("đỉnh nguồn")
if idx2 != -1:
    print("FOUND: ", full_text[idx2-50:idx2+50].replace('\n', ' '))
else:
    print("NOT FOUND 'đỉnh nguồn'")
