"""
core/evaluation/ragas_eval.py
RAGAS evaluation pipeline using local Ollama models (ChatOllama & OllamaEmbeddings).
Evaluates faithfulness, answer relevance, context recall, and context precision.
"""
import sys
import types

# ── Mocking VertexAI module to fix Ragas v0.4.3 compatibility bug ─────────────
if "langchain_community.chat_models.vertexai" not in sys.modules:
    class DummyModule(types.ModuleType):
        pass
    vertexai_module = DummyModule("langchain_community.chat_models.vertexai")
    vertexai_module.ChatVertexAI = type("ChatVertexAI", (object,), {})
    sys.modules["langchain_community.chat_models.vertexai"] = vertexai_module
# ──────────────────────────────────────────────────────────────────────────────

from datasets import Dataset
from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision
from langchain_ollama import ChatOllama, OllamaEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from utils.config import get_config
from core.retrieval.hybrid_retriever import search
from core.pipeline.answer_generator import generate_with_context
from core.pipeline.agentic_rag import evaluate_chunks
import re

def clean_json_string(text: str) -> str:
    text = text.strip()
    # If the response is wrapped in markdown code blocks, extract it
    if "```json" in text:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    elif "```" in text:
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    
    # Otherwise, find the first '{' and last '}' and extract
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end+1].strip()
    
    # For lists/arrays
    start_arr = text.find("[")
    end_arr = text.rfind("]")
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        return text[start_arr:end_arr+1].strip()
        
    return text

class JSONCleaningChatOllama(ChatOllama):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # Call the original _generate method
        result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        
        # Clean the message content in the result
        if result.generations:
            for gen in result.generations:
                if hasattr(gen, "message") and hasattr(gen.message, "content"):
                    raw_content = gen.message.content
                    cleaned = clean_json_string(raw_content)
                    if cleaned != raw_content:
                        print(f"[RAGAS LLM CLEAN] Cleaned JSON from local LLM response:\n--- Raw ---\n{raw_content[:200]}...\n--- Cleaned ---\n{cleaned[:200]}...\n-----------")
                        gen.message.content = cleaned
                        if hasattr(gen, "text"):
                            gen.text = cleaned
        return result

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        result = await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        if result.generations:
            for gen in result.generations:
                if hasattr(gen, "message") and hasattr(gen.message, "content"):
                    raw_content = gen.message.content
                    cleaned = clean_json_string(raw_content)
                    if cleaned != raw_content:
                        print(f"[RAGAS LLM CLEAN] Cleaned JSON from async local LLM response")
                        gen.message.content = cleaned
                        if hasattr(gen, "text"):
                            gen.text = cleaned
        return result

def evaluate_pipeline(test_dataset: list[dict], subject_id: str) -> dict:
    """
    Evaluate the RAG pipeline using RAGAS.
    test_dataset: list of {"question": "...", "ground_truth": "..."}
    subject_id: e.g., 'dsa'
    
    Returns evaluation result dict with metric scores.
    """
    cfg = get_config()
    
    # 1. Initialize local LLM and Embeddings wrappers for Ragas
    llm = JSONCleaningChatOllama(
        model=cfg["llm"]["model"],
        base_url=cfg["llm"]["base_url"],
        temperature=0.0,
        timeout=300
    )
    embeddings = OllamaEmbeddings(
        model=cfg["embedding"]["model"],
        base_url=cfg["embedding"]["base_url"]
    )
    
    ragas_llm = LangchainLLMWrapper(llm)
    ragas_emb = LangchainEmbeddingsWrapper(embeddings)
    
    # 2. Run test dataset through our RAG pipeline to collect fields
    eval_data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": []
    }
    
    for item in test_dataset:
        q = item["question"]
        gt = item["ground_truth"]
        
        print(f"\n[RAGAS EVAL] Running RAG query: '{q}'...")
        # A. Retrieve context chunks
        chunks, _ = search(q, subject_id, top_k=5)
        
        # B. Filter using CRAG evaluate_chunks
        relevant_chunks = evaluate_chunks(q, chunks)
        contexts = [c["text"] for c in relevant_chunks]
        
        # C. Generate answer from LLM (blocking mode)
        ans = generate_with_context(q, relevant_chunks, stream=False)
        
        # Clean answer to remove sources block for evaluation purity if needed
        # (Though Ragas can evaluate the full response)
        eval_data["question"].append(q)
        eval_data["answer"].append(ans)
        eval_data["contexts"].append(contexts)
        eval_data["ground_truth"].append(gt)
        
    # 3. Create HuggingFace Dataset
    dataset = Dataset.from_dict(eval_data)
    
    # 4. Evaluate using Ragas
    print("\n[RAGAS EVAL] Running Ragas metrics evaluation (using local Ollama models sequentially)...")
    run_config = RunConfig(max_workers=1, timeout=300)
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        llm=ragas_llm,
        embeddings=ragas_emb,
        run_config=run_config
    )
    
    return result
