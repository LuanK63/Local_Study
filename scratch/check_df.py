"""
scratch/check_df.py
Diagnostic script to print columns returned by Ragas evaluate.to_pandas()
"""
import sys
import types

# Mock VertexAI
class DummyModule(types.ModuleType):
    pass
vertexai_module = DummyModule('langchain_community.chat_models.vertexai')
vertexai_module.ChatVertexAI = type('ChatVertexAI', (object,), {})
sys.modules['langchain_community.chat_models.vertexai'] = vertexai_module

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_ollama import ChatOllama, OllamaEmbeddings

def main():
    llm = LangchainLLMWrapper(ChatOllama(model='qwen2.5-coder:7b'))
    emb = LangchainEmbeddingsWrapper(OllamaEmbeddings(model='nomic-embed-text'))
    ds = Dataset.from_dict({
        'question': ['ngăn xếp là gì'], 
        'answer': ['ngăn xếp là stack'], 
        'contexts': [['ngăn xếp là một danh sách LIFO']], 
        'ground_truth': ['ngăn xếp là kiểu danh sách LIFO']
    })
    print("Evaluating...")
    r = evaluate(ds, metrics=[faithfulness], llm=llm, embeddings=emb)
    df = r.to_pandas()
    print("DataFrame Columns:", list(df.columns))
    print("DataFrame Content:\n", df)

if __name__ == "__main__":
    main()
