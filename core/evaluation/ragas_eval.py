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

import math
import time
import re
from datasets import Dataset
from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision
from langchain_ollama import OllamaEmbeddings, ChatOllama
from core.evaluation.evaluation_config import JUDGE_MODEL, TEMPERATURE, NUM_CTX, TIMEOUT
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from utils.config import get_config
from core.retrieval.hybrid_retriever import search
from core.pipeline.answer_generator import generate_with_context
from core.pipeline.agentic_rag import evaluate_chunks


class PatchedChatOllama(ChatOllama):
    def _clean_content(self, text: str) -> str:
        text = text.strip()
        # Trích xuất nội dung từ khối mã markdown nếu có
        code_block = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
        if code_block:
            text = code_block.group(1).strip()
        # Nếu chuỗi không bắt đầu bằng { hoặc [ nhưng có chứa chúng, thử trích xuất phần JSON
        if not (text.startswith('{') or text.startswith('[')):
            json_struct = re.search(r'([\[{][\s\S]*[\]}])', text)
            if json_struct:
                text = json_struct.group(1).strip()
        return text

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        res = super()._generate(messages, stop, run_manager, **kwargs)
        for gen in res.generations:
            gen.message.content = self._clean_content(gen.message.content)
            gen.text = gen.message.content
        return res

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        res = await super()._agenerate(messages, stop, run_manager, **kwargs)
        for gen in res.generations:
            gen.message.content = self._clean_content(gen.message.content)
            gen.text = gen.message.content
        return res


def evaluate_pipeline(test_dataset: list[dict], subject_id: str, run_id: int = None) -> dict:
    """
    Evaluate the RAG pipeline using RAGAS.
    test_dataset: list of {"question": "...", "ground_truth": "...", "expected_sources": [...]}
    subject_id: e.g., 'dsa'
    run_id: Optional ID of the current experiment run to save results.
    
    Returns evaluation result dict with metric scores.
    """
    cfg = get_config()
    
    # 1. Initialize local ChatOllama LLM and local Embeddings wrappers for Ragas
    llm = PatchedChatOllama(
        model=JUDGE_MODEL,
        temperature=TEMPERATURE,
        num_ctx=NUM_CTX,
        base_url=cfg["llm"]["base_url"],
        timeout=TIMEOUT
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
    
    custom_metrics = []
    
    for item in test_dataset:
        q = item["question"]
        gt = item["ground_truth"]
        expected_sources = item.get("expected_sources", [])
        
        print(f"\n[RAGAS EVAL] Running RAG query: '{q}'...")
        
        # Measure retrieval time
        start_ret = time.time()
        # Retrieve 10 chunks to calculate Recall@10/Precision@10
        chunks_10, _ = search(q, subject_id, top_k=10)
        retrieval_time_s = time.time() - start_ret
        
        # Filter top 5 chunks using CRAG
        chunks_5 = chunks_10[:5]
        relevant_chunks = evaluate_chunks(q, chunks_5)
        contexts = [c["text"] for c in relevant_chunks]
        
        # Measure generation time
        start_gen = time.time()
        ans = generate_with_context(q, relevant_chunks, stream=False)
        generation_time_s = time.time() - start_gen
        total_time_s = retrieval_time_s + generation_time_s
        
        # Calculate custom IR metrics (Recall@5, Recall@10, Precision@5, Precision@10)
        from experiments.metrics_collector import calculate_precision_recall_k
        p5, r5 = calculate_precision_recall_k(chunks_10, expected_sources, 5)
        p10, r10 = calculate_precision_recall_k(chunks_10, expected_sources, 10)
        
        eval_data["question"].append(q)
        eval_data["answer"].append(ans)
        eval_data["contexts"].append(contexts)
        eval_data["ground_truth"].append(gt)
        
        custom_metrics.append({
            "precision_5": p5,
            "recall_5": r5,
            "precision_10": p10,
            "recall_10": r10,
            "retrieval_time_s": retrieval_time_s,
            "generation_time_s": generation_time_s,
            "total_time_s": total_time_s
        })
        
    # 3. Create HuggingFace Dataset
    dataset = Dataset.from_dict(eval_data)
    
    # 4. Evaluate using Ragas
    print("\n[RAGAS EVAL] Running Ragas metrics evaluation (using ChatOllama model sequentially)...")
    run_config = RunConfig(max_workers=1, timeout=TIMEOUT)
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        llm=ragas_llm,
        embeddings=ragas_emb,
        run_config=run_config,
        raise_exceptions=False
    )
    
    # 5. Save results to Database
    df = result.to_pandas()
    from utils.experiment_logger import log_query_result
    
    if run_id is not None:
        for idx, row in df.iterrows():
            metrics = custom_metrics[idx]
            
            # Extract RAGAS metrics, replacing NaN with 0.0
            def clean_val(val):
                return float(val) if (isinstance(val, (int, float)) and not math.isnan(val)) else 0.0

            f_score = clean_val(row.get("faithfulness", 0.0))
            ar_score = clean_val(row.get("answer_relevancy", 0.0))
            cr_score = clean_val(row.get("context_recall", 0.0))
            cp_score = clean_val(row.get("context_precision", 0.0))
            
            log_query_result(
                run_id=run_id,
                subject_id=subject_id,
                question=row.get("question", row.get("user_input", "")),
                answer=row.get("answer", row.get("response", "")),
                faithfulness=f_score,
                answer_relevancy=ar_score,
                context_recall=cr_score,
                context_precision=cp_score,
                recall_at_5=metrics["recall_5"],
                recall_at_10=metrics["recall_10"],
                precision_at_5=metrics["precision_5"],
                precision_at_10=metrics["precision_10"],
                retrieval_time_s=metrics["retrieval_time_s"],
                generation_time_s=metrics["generation_time_s"],
                total_time_s=metrics["total_time_s"]
            )
            
        # Update run averages in the database
        from utils.experiment_logger import update_run_averages
        update_run_averages(run_id)
        
    return result
