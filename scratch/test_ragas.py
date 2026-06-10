"""
scratch/test_ragas.py
Verify RAGAS imports with corrected metric names.
"""
import sys
import types

# Reconfigure stdout to use UTF-8
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ── Mocking VertexAI module to fix Ragas v0.4.3 compatibility bug ─────────────
class DummyModule(types.ModuleType):
    pass

vertexai_module = DummyModule("langchain_community.chat_models.vertexai")
vertexai_module.ChatVertexAI = type("ChatVertexAI", (object,), {})
sys.modules["langchain_community.chat_models.vertexai"] = vertexai_module
# ──────────────────────────────────────────────────────────────────────────────

sys.path.append("c:\\Users\\LUAN\\Desktop\\Local_Study_RAG_Agent")

def main():
    print("=== TESTING RAGAS IMPORTS ===")
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision
        from datasets import Dataset
        from langchain_ollama import ChatOllama, OllamaEmbeddings
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        
        print("Imports successful!")
        
        # Test initialization
        llm = ChatOllama(model="qwen2.5-coder:7b", base_url="http://localhost:11434")
        embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434")
        
        ragas_llm = LangchainLLMWrapper(llm)
        ragas_emb = LangchainEmbeddingsWrapper(embeddings)
        print("Initialization of Langchain-Ollama wrappers successful!")
        
    except Exception as e:
        import traceback
        print(f"Error during import/init:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
