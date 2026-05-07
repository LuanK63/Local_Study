"""
modules/flashcard_system.py — M9
Create, manage, and export flashcards to Anki (.apkg).
"""
import json
import genanki
import random
from pathlib import Path
from datetime import datetime
from core.pipeline.answer_generator import generate
from utils.db_schema import get_connection


# ── Generate flashcards from topic ───────────────────────────────────────────
SYSTEM = (
    "Tạo flashcard học tập theo định dạng JSON:\n"
    '[\n  {"front": "Câu hỏi/khái niệm", "back": "Câu trả lời ngắn gọn"}\n]\n'
    "Chỉ trả về JSON. Front nên là câu hỏi ngắn, Back là câu trả lời rõ ràng."
)


def generate_flashcards(topic: str, subject_id: str, count: int = 10) -> list[dict]:
    """Generate flashcards from a topic using LLM."""
    from core.retrieval.hybrid_retriever import hybrid_search
    import re

    chunks = hybrid_search(topic, subject_id, top_k=4)
    context = "\n\n".join(c["text"] for c in chunks)

    user = (
        f"Chủ đề: {topic}\n"
        f"Tài liệu:\n{context}\n\n"
        f"Tạo {count} flashcard."
    )
    raw = generate(SYSTEM, user, stream=False)

    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not match:
        return []
    try:
        cards = json.loads(match.group())
        return cards
    except json.JSONDecodeError:
        return []


# ── CRUD ─────────────────────────────────────────────────────────────────────
def save_flashcards(cards: list[dict], subject_id: str, source: str = ""):
    conn = get_connection()
    now = datetime.now().isoformat()
    for c in cards:
        conn.execute(
            "INSERT INTO flashcards (subject_id, front, back, source, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (subject_id, c["front"], c["back"], source, now)
        )
    conn.commit()
    conn.close()


def get_flashcards(subject_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, front, back, source, created_at FROM flashcards WHERE subject_id = ?",
        (subject_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_flashcard(card_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM flashcards WHERE id = ?", (card_id,))
    conn.commit()
    conn.close()


# ── Anki Export ───────────────────────────────────────────────────────────────
def export_to_anki(subject_id: str, output_path: str = "data/flashcards.apkg") -> str:
    """Export all flashcards for a subject to an Anki .apkg file."""
    cards = get_flashcards(subject_id)
    if not cards:
        raise ValueError("Không có flashcard nào để export")

    model = genanki.Model(
        random.randrange(1 << 30, 1 << 31),
        f"Study Agent — {subject_id}",
        fields=[{"name": "Front"}, {"name": "Back"}],
        templates=[{
            "name": "Card",
            "qfmt": "{{Front}}",
            "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
        }],
    )
    deck = genanki.Deck(random.randrange(1 << 30, 1 << 31), f"Study Agent / {subject_id}")

    for c in cards:
        note = genanki.Note(model=model, fields=[c["front"], c["back"]])
        deck.add_note(note)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(deck).write_to_file(output_path)
    return output_path
