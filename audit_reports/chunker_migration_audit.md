# Phase 12: Chunker Migration Audit

- **SemanticChunker**: Checked `core/document_processor/`. No active references found in entrypoints.
- **Embedding-based Logic**: Still present in `pdf_processor.py` but isolated.
- **Dead Path**: Found legacy `chunker.py` methods that are superseded by `heuristic_chunker.py`.
