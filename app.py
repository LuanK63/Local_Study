"""
app.py — Entry point for Local Study RAG Agent
Run with: streamlit run app.py
"""
import streamlit as st
from utils.subject_loader import get_all_subjects
from utils.db_schema import init_db

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Study RAG Agent",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Init DB on first run ────────────────────────────────────────────────────────
init_db()

# ── Load subjects ───────────────────────────────────────────────────────────────
subjects = get_all_subjects()

# ── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎓 Study RAG Agent")
    st.markdown("---")

    # Subject switcher
    st.subheader("📚 Môn học")
    subject_options = {sid: cfg.display_name for sid, cfg in subjects.items()}
    if not subject_options:
        st.error("Không tìm thấy môn học nào. Thêm thư mục vào subjects/")
        st.stop()

    selected_id = st.selectbox(
        "Chọn môn:",
        options=list(subject_options.keys()),
        format_func=lambda x: subject_options[x],
        key="selected_subject",
    )
    subject = subjects[selected_id]

    st.markdown("---")
    st.caption(f"📂 Collection: `{subject.chroma_collection}`")
    st.caption(f"💻 Sandbox: `{'C/C++' if subject.code_language == 'c_cpp' else 'Python'}`")
    st.caption(f"🌐 Ngôn ngữ tài liệu: `{', '.join(subject.languages).upper()}`")

# ── Tabs ─────────────────────────────────────────────────────────────────────────
TAB_LABELS = ["📖 Giải thích", "💻 Code", "▶️ Sandbox", "📝 Quiz",
              "🎯 Luyện tập", "🃏 Flashcard", "🗺️ Lộ trình", "⚠️ Điểm yếu"]

if subject.has_visualizer:
    TAB_LABELS.insert(1, "🌳 Visualizer")

tabs = st.tabs(TAB_LABELS)

# ── Tab routing ──────────────────────────────────────────────────────────────────
tab_idx = 0

with tabs[tab_idx]:  # Giải thích
    st.header("📖 Concept Explainer")
    st.info("Module đang được xây dựng — Sprint 3")
tab_idx += 1

if subject.has_visualizer:
    with tabs[tab_idx]:  # Visualizer (DSA only)
        st.header("🌳 Algorithm Visualizer")
        st.info("Module đang được xây dựng — Sprint 5")
    tab_idx += 1

with tabs[tab_idx]:  # Code
    st.header("💻 Code Generator / Explainer")
    st.info("Module đang được xây dựng — Sprint 3")
tab_idx += 1

with tabs[tab_idx]:  # Sandbox
    st.header("▶️ Code Sandbox")
    st.info("Module đang được xây dựng — Sprint 4")
tab_idx += 1

with tabs[tab_idx]:  # Quiz
    st.header("📝 Quiz Generator")
    st.info("Module đang được xây dựng — Sprint 6")
tab_idx += 1

with tabs[tab_idx]:  # Practice
    st.header("🎯 Practice Mode")
    st.info("Module đang được xây dựng — Sprint 6")
tab_idx += 1

with tabs[tab_idx]:  # Flashcard
    st.header("🃏 Flashcard System")
    st.info("Module đang được xây dựng — Sprint 7")
tab_idx += 1

with tabs[tab_idx]:  # Learning Path
    st.header("🗺️ Learning Path Generator")
    st.info("Module đang được xây dựng — Sprint 7")
tab_idx += 1

with tabs[tab_idx]:  # Weakness
    st.header("⚠️ Weakness Detection")
    st.info("Module đang được xây dựng — Sprint 7")
