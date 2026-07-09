"""
modules/learning_path.py — M10
Generate personalized learning roadmap based on subject topics + detected weaknesses.
"""
import json
from utils.subject_loader import get_subject
from modules.weakness_detector import get_weak_topics
from core.pipeline.answer_generator import generate


SYSTEM = (
    "Bạn là cố vấn học tập chuyên nghiệp. Hãy tạo lộ trình học tập cá nhân hóa.\n"
    "Lộ trình cần:\n"
    "1. Thứ tự học từng chủ đề (dựa trên dependency)\n"
    "2. Ưu tiên các chủ đề còn yếu\n"
    "3. Ước tính thời gian cho mỗi chủ đề\n"
    "4. Gợi ý tài nguyên/bài tập cụ thể\n"
    "Dùng Markdown với bảng và checklist."
)


def generate_learning_path(subject_id: str) -> str:
    """Generate personalized path combining topic order + user weaknesses."""
    subject = get_subject(subject_id)
    weak = get_weak_topics(subject_id)

    # Build topic list with phase info
    topic_lines = []
    for t in subject.topics:
        weak_info = next((w for w in weak if w["topic_id"] == t["id"]), None)
        status = f" Yếu ({weak_info['wrong_rate']*100:.0f}%)" if weak_info and weak_info["wrong_rate"] > 0.4 else ""
        topic_lines.append(
            f"- [{status}] Phase {t['phase']}: {t['name']} (id: {t['id']})"
        )

    weak_lines = [
        f"- {w['topic_id']}: {w['wrong_rate']*100:.0f}% sai ({w['attempts']} lần làm)"
        for w in weak[:5]
    ] if weak else ["- Chưa có dữ liệu"]

    user = (
        f"Môn học: {subject.name}\n\n"
        f"Danh sách topic theo thứ tự chuẩn:\n" + "\n".join(topic_lines) +
        f"\n\nĐiểm yếu phát hiện:\n" + "\n".join(weak_lines) +
        f"\n\nTạo lộ trình học tập cá nhân hóa."
    )
    return generate(SYSTEM, user, stream=False)


def generate_learning_path_stream(subject_id: str):
    subject = get_subject(subject_id)
    weak = get_weak_topics(subject_id)

    topic_lines = [f"- Phase {t['phase']}: {t['name']}" for t in subject.topics]
    weak_lines = [f"- {w['topic_id']}: {w['wrong_rate']*100:.0f}% sai" for w in weak[:5]] or ["- Chưa có"]

    user = (
        f"Môn học: {subject.name}\n\n"
        f"Topics:\n" + "\n".join(topic_lines) +
        f"\n\nĐiểm yếu:\n" + "\n".join(weak_lines) +
        f"\n\nTạo lộ trình học tập."
    )
    return generate(SYSTEM, user, stream=True)
