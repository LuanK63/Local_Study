import sys
import os
sys.path.append('c:/Users/LUAN/Desktop/Local_Study_RAG_Agent')
from core.pipeline.agentic_rag import generate_agentic_response

class DummyCfg:
    prompt_hints = {}

res = list(generate_agentic_response('What is a binary search tree?', 'dsa', DummyCfg()))
print('\n--- RESULT ---\n', ''.join(res))
