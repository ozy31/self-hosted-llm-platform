# 03 — Document RAG on KEDA docs: baseline vs RAG (2026-11-02)

Setup: 10 KEDA 2.22 doc pages (concepts + 7 scalers, ~17k words) · embeddings nomic-embed-text via Ollama · cosine search in pure Python ·
answers by `ozai` (qwen3:8b, thinking off, temperature 0) through LiteLLM · script: rag/ozai_rag.py · questions: rag/eval_keda.json.
Scoring: an answer passes only if every expected term appears (e.g. all three RabbitMQ modes). Strict and repeatable, but crude.

| Config | Chunks | Accuracy | Avg latency | Avg prompt tokens |
|---|---|---|---|---|
| No RAG (model memory only) | – | 1/10 | ~17.5 s | 31 |
| v1: 300-word chunks, top-4, embeddings only | 120 | 6/10 | 9.2 s | 1264 |
| v2a: 150-word chunks, top-6, embeddings only | 165 | 6/10 | 7.7 s | – |
| **v2b: 150-word chunks, top-6, hybrid (embeddings + IDF keyword, weight 0.3)** | 165 | **8/10** | 9.9 s | 1487 |

Findings
- Without RAG the model invents defaults and parameter names with confidence (1/10).
- RAG answers were also *faster*: short cited answers instead of long invented ones.
- v1 failures were retrieval misses: the right section, but the chunk with the parameter list was not in the top 4.
- Smaller chunks alone changed nothing (6/10). Hybrid keyword scoring added +2: questions contain exact identifiers
  (`lagThreshold`, `mode`, `protocol`) that embeddings match poorly.
- Remaining 2 failures are model reasoning, not retrieval: it inferred "default protocol = HTTP" from the examples (docs say `auto`),
  and listed RabbitMQ modes incompletely.
- Next experiments: ozai-think on the failures; a reranker; a larger model on GPU (article 3).
