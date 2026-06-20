import sys
import os

sys.path.append(os.getcwd())

from core.pipeline.agentic_rag import AgentState
from core.pipeline.retrieval_grader import grade_documents

print("Starting test_grader.py verification...")

# Initialize mock AgentState
state = AgentState(
    query="Linked List là gì?",
    rag_mode="rag_grader",
    chunking_strategy="fixed",
    question_id=1
)

# --- Test Case A ---
print("\n--- Running Case A (Relevant Content) ---")
chunks_a = [
    {
        "doc_name": "dsa_lecture.pdf",
        "page_num": 12,
        "text": "Linked List (Danh sách liên kết) là cấu trúc dữ liệu tuyến tính bao gồm các nút (nodes). Mỗi nút chứa dữ liệu và liên kết đến nút tiếp theo trong chuỗi."
    }
]

res_a = grade_documents(state.query, chunks_a)
score_a = res_a["score"]
explanation_a = res_a["explanation"]

# Integrate to AgentState
state.grader_score_l1 = score_a
state.grader_explanation_l1 = explanation_a
state.retrieval_success_grader_l1 = 1 if score_a >= 3 else 0

print("Case A Grader Output:")
print("  Score:                        ", state.grader_score_l1)
print("  Retrieval Success Grader L1:  ", state.retrieval_success_grader_l1)
print("  Explanation:                  ", state.grader_explanation_l1)

assert state.grader_score_l1 >= 3, f"Expected score >= 3, got {state.grader_score_l1}"
assert state.retrieval_success_grader_l1 == 1, "Expected success to be 1"
print("Case A PASSED!")


# --- Test Case B ---
print("\n--- Running Case B (Irrelevant Content) ---")
chunks_b = [
    {
        "doc_name": "networking.pdf",
        "page_num": 45,
        "text": "TCP/IP là bộ giao thức mạng được sử dụng để truyền dữ liệu trên Internet. Nó bao gồm tầng ứng dụng, tầng giao vận, tầng mạng và tầng truy cập mạng."
    }
]

res_b = grade_documents(state.query, chunks_b)
score_b = res_b["score"]
explanation_b = res_b["explanation"]

# Integrate to AgentState
state.grader_score_l1 = score_b
state.grader_explanation_l1 = explanation_b
state.retrieval_success_grader_l1 = 1 if score_b >= 3 else 0

print("Case B Grader Output:")
print("  Score:                        ", state.grader_score_l1)
print("  Retrieval Success Grader L1:  ", state.retrieval_success_grader_l1)
print("  Explanation:                  ", state.grader_explanation_l1)

assert state.grader_score_l1 <= 2, f"Expected score <= 2, got {state.grader_score_l1}"
assert state.retrieval_success_grader_l1 == 0, "Expected success to be 0"
print("Case B PASSED!")

print("\nAll cases validated successfully!")
