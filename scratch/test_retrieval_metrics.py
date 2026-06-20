import sys
import os

sys.path.append(os.getcwd())

from core.pipeline.agentic_rag import AgentState
from utils.retrieval_metrics import compute_retrieval_metrics

print("Starting test_retrieval_metrics.py validation...")

# Initialize mock AgentState
state = AgentState(
    query="Test Query",
    rag_mode="pure_rag",
    chunking_strategy="fixed",
    question_id=1
)

# Case A: Ground Truth = pages [10], docs ["lecture1.pdf"]
print("\n--- Running Case A ---")
gt_docs_a = ["lecture1.pdf"]
gt_pages_a = [10]

retrieved_chunks_a = [
    {"doc_name": "lecture1.pdf", "page_num": 10},  # Rank 1: Match
    {"doc_name": "lecture1.pdf", "page_num": 11},  # Rank 2: No match
    {"doc_name": "lecture2.pdf", "page_num": 10},  # Rank 3: No match
]

metrics_a = compute_retrieval_metrics(retrieved_chunks_a, gt_docs_a, gt_pages_a)

# Integrate/assign to L1 in state
state.hit_at_1_l1 = metrics_a["hit_at_1"]
state.hit_at_3_l1 = metrics_a["hit_at_3"]
state.hit_at_5_l1 = metrics_a["hit_at_5"]
state.recall_at_1_l1 = metrics_a["recall_at_1"]
state.recall_at_3_l1 = metrics_a["recall_at_3"]
state.recall_at_5_l1 = metrics_a["recall_at_5"]
state.first_relevant_rank_l1 = metrics_a["first_relevant_rank"]

print("Case A Results:")
print("  Hit@1 L1:", state.hit_at_1_l1)
print("  Hit@3 L1:", state.hit_at_3_l1)
print("  Hit@5 L1:", state.hit_at_5_l1)
print("  Recall@1 L1:", state.recall_at_1_l1)
print("  Recall@3 L1:", state.recall_at_3_l1)
print("  Recall@5 L1:", state.recall_at_5_l1)
print("  First Relevant Rank L1:", state.first_relevant_rank_l1)

# Assertions for Case A
assert state.hit_at_1_l1 == 1
assert state.hit_at_3_l1 == 1
assert state.hit_at_5_l1 == 1
assert state.recall_at_1_l1 == 1.0
assert state.recall_at_3_l1 == 1.0
assert state.recall_at_5_l1 == 1.0
assert state.first_relevant_rank_l1 == 1
print("Case A PASSED!")


# Case B: Ground Truth = pages [10, 11, 12], docs ["lecture1.pdf"]
print("\n--- Running Case B ---")
gt_docs_b = ["lecture1.pdf"]
gt_pages_b = [10, 11, 12]

retrieved_chunks_b = [
    {"doc_name": "lecture1.pdf", "page_num": 9},   # Rank 1: No match
    {"doc_name": "lecture1.pdf", "page_num": 10},  # Rank 2: Match
    {"doc_name": "lecture2.pdf", "page_num": 11},  # Rank 3: No match
    {"doc_name": "lecture1.pdf", "page_num": 12},  # Rank 4: Match
    {"doc_name": "lecture1.pdf", "page_num": 15},  # Rank 5: No match
]

metrics_b = compute_retrieval_metrics(retrieved_chunks_b, gt_docs_b, gt_pages_b)

# Integrate/assign to L2 in state (demonstrating L2 integration)
state.hit_at_1_l2 = metrics_b["hit_at_1"]
state.hit_at_3_l2 = metrics_b["hit_at_3"]
state.hit_at_5_l2 = metrics_b["hit_at_5"]
state.recall_at_1_l2 = metrics_b["recall_at_1"]
state.recall_at_3_l2 = metrics_b["recall_at_3"]
state.recall_at_5_l2 = metrics_b["recall_at_5"]
state.first_relevant_rank_l2 = metrics_b["first_relevant_rank"]

print("Case B Results:")
print("  Hit@1 L2:", state.hit_at_1_l2)
print("  Hit@3 L2:", state.hit_at_3_l2)
print("  Hit@5 L2:", state.hit_at_5_l2)
print("  Recall@1 L2:", state.recall_at_1_l2)
print("  Recall@3 L2:", state.recall_at_3_l2)
print("  Recall@5 L2:", state.recall_at_5_l2)
print("  First Relevant Rank L2:", state.first_relevant_rank_l2)

# Assertions for Case B
assert state.hit_at_1_l2 == 0
assert state.hit_at_3_l2 == 1
assert state.hit_at_5_l2 == 1
# Total Ground Truth pairs: ('lecture1', 10), ('lecture1', 11), ('lecture1', 12) -> total 3
# In top 1, found 0. Recall = 0.0
# In top 3, found ('lecture1', 10). Recall = 1 / 3 = 0.3333333333333333
# In top 5, found ('lecture1', 10) and ('lecture1', 12). Recall = 2 / 3 = 0.6666666666666666
assert abs(state.recall_at_1_l2 - 0.0) < 1e-6
assert abs(state.recall_at_3_l2 - (1.0 / 3)) < 1e-6
assert abs(state.recall_at_5_l2 - (2.0 / 3)) < 1e-6
assert state.first_relevant_rank_l2 == 2
print("Case B PASSED!")


# Case C: No Match
print("\n--- Running Case C ---")
gt_docs_c = ["lecture1.pdf"]
gt_pages_c = [10]

retrieved_chunks_c = [
    {"doc_name": "lecture2.pdf", "page_num": 10},
    {"doc_name": "lecture1.pdf", "page_num": 11},
]

metrics_c = compute_retrieval_metrics(retrieved_chunks_c, gt_docs_c, gt_pages_c)

print("Case C Results:")
print("  Hit@5:", metrics_c["hit_at_5"])
print("  Recall@5:", metrics_c["recall_at_5"])
print("  First Relevant Rank:", metrics_c["first_relevant_rank"])

assert metrics_c["hit_at_1"] == 0
assert metrics_c["hit_at_5"] == 0
assert metrics_c["recall_at_5"] == 0.0
assert metrics_c["first_relevant_rank"] == 999
print("Case C PASSED!")

print("\nAll cases validated successfully!")
