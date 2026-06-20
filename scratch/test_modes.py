import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from core.pipeline.agentic_rag import AgentState, generate_agentic_response
from utils.config import get_config

# Dummy subject config
class DummySubjectCfg:
    prompt_hints = {"top_k": 5}

subject_cfg = DummySubjectCfg()

def run_test():
    cfg = get_config()
    if "rag" not in cfg:
        cfg["rag"] = {}
        
    # Mock retrieval search, grader, rewrite, and generation
    with patch("core.pipeline.agentic_rag.retrieval_search") as mock_search, \
         patch("core.pipeline.retrieval_grader.grade_documents") as mock_grade, \
         patch("core.pipeline.agentic_rag.rewrite_query") as mock_rewrite, \
         patch("core.pipeline.answer_generator.generate_with_context") as mock_gen:
         
        # Set up default returns
        mock_search.return_value = ([{"doc_name": "doc1.pdf", "page_num": 1, "text": "text1", "score": 0.25}], "hybrid")
        mock_grade.return_value = {"score": 4, "explanation": "Good docs"}
        mock_rewrite.return_value = "rewritten query"
        mock_gen.return_value = "Mock answer"

        # ----------------------------------------------------
        # CASE A: pure_rag mode
        # ----------------------------------------------------
        print("\n=== Testing CASE A: pure_rag ===")
        cfg["rag"]["mode"] = "pure_rag"
        cfg["rag"]["enable_crag"] = True
        
        state_a = AgentState("Linked List là gì?", "pure_rag", "fixed", 1)
        # Consume the generator to run the pipeline
        list(generate_agentic_response("Linked List là gì?", "dsa", subject_cfg, state=state_a))
        
        print("Grader call count:   ", mock_grade.call_count)
        print("Rewrite call count:  ", mock_rewrite.call_count)
        print("Attempts:            ", state_a.attempts)
        print("Rewrite activated:   ", state_a.rewrite_activated)
        
        assert mock_grade.call_count == 0, "Grader should NOT run in pure_rag!"
        assert mock_rewrite.call_count == 0, "Rewrite should NOT run in pure_rag!"
        assert state_a.attempts == 1
        assert state_a.rewrite_activated == 0
        print("CASE A PASSED!")

        # Reset mock counts
        mock_grade.reset_mock()
        mock_rewrite.reset_mock()

        # ----------------------------------------------------
        # CASE B: rag_grader mode
        # ----------------------------------------------------
        print("\n=== Testing CASE B: rag_grader ===")
        cfg["rag"]["mode"] = "rag_grader"
        
        state_b = AgentState("Linked List là gì?", "rag_grader", "fixed", 2)
        list(generate_agentic_response("Linked List là gì?", "dsa", subject_cfg, state=state_b))
        
        print("Grader call count:   ", mock_grade.call_count)
        print("Rewrite call count:  ", mock_rewrite.call_count)
        print("Attempts:            ", state_b.attempts)
        print("Rewrite activated:   ", state_b.rewrite_activated)
        
        assert mock_grade.call_count == 1, "Grader should run exactly once in rag_grader!"
        assert mock_rewrite.call_count == 0, "Rewrite should NOT run in rag_grader!"
        assert state_b.attempts == 1
        assert state_b.rewrite_activated == 0
        print("CASE B PASSED!")

        # Reset mock counts
        mock_grade.reset_mock()
        mock_rewrite.reset_mock()

        # ----------------------------------------------------
        # CASE C: agentic_light mode (with low similarity -> rewrite triggers)
        # ----------------------------------------------------
        print("\n=== Testing CASE C: agentic_light (low sim -> triggers rewrite) ===")
        cfg["rag"]["mode"] = "agentic_light"
        cfg["rag"]["rewrite_similarity_threshold"] = 0.40
        # Search returns low score chunk (0.25 < 0.40)
        mock_search.return_value = ([{"doc_name": "doc1.pdf", "page_num": 1, "text": "text1", "score": 0.25}], "hybrid")
        
        state_c = AgentState("Linked List là gì?", "agentic_light", "fixed", 3)
        list(generate_agentic_response("Linked List là gì?", "dsa", subject_cfg, state=state_c))
        
        print("Grader call count:   ", mock_grade.call_count)
        print("Rewrite call count:  ", mock_rewrite.call_count)
        print("Attempts:            ", state_c.attempts)
        print("Rewrite activated:   ", state_c.rewrite_activated)
        print("Rewritten Query:     ", state_c.rewritten_query)
        
        # Grader runs twice: once for L1, once for L2
        assert mock_grade.call_count == 2, "Grader should run twice (L1 and L2) when rewrite triggers!"
        assert mock_rewrite.call_count == 1, "Rewrite should run exactly once!"
        assert state_c.attempts == 2, "Attempts should be 2 after rewrite!"
        assert state_c.rewrite_activated == 1, "Rewrite activated flag should be 1!"
        assert state_c.rewritten_query == "rewritten query"
        print("CASE C PASSED!")

if __name__ == "__main__":
    run_test()
    print("\nAll Mode Orchestrator tests passed successfully!")
