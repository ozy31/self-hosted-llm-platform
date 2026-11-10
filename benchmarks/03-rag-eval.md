# 03 — Document RAG on KEDA docs: baseline vs RAG (2026-11-02)

Setup: 10 KEDA 2.22 doc pages (concepts + 7 scalers, ~17k words) · embeddings nomic-embed-text via Ollama · cosine search in pure Python ·
answers by `ozai` (qwen3:8b, thinking off, temperature 0) through LiteLLM · script: rag/ozai_rag.py · questions: rag/eval_keda.json.
Scoring: an answer passes only if every expected term appears (e.g. all three RabbitMQ modes). Strict and repeatable, but crude.

| Config | Chunks | Accuracy | Avg latency | Avg prompt tokens |
|---|---|---|---|---|
| No RAG (model memory only) | – | 1/10 | ~17.5 s | 31 |
| v1: 300-word chunks, top-4, embeddings only | 120 | 6/10 | 9.2 s | 1264 |
| v2a: 150-word chunks, top-6, embeddings only | 165 | 6/10 | 7.7 s | – |
| v2b: 150-word chunks, top-6, hybrid (embeddings + IDF keyword, weight 0.3) | 165 | 8/10 | 9.9 s | 1487 |
| **v3: v2b + MMR diversity (λ 0.7)** (2026-11-10) | 165 | **9/10** | 10.6 s | 1413 |

Findings
- Without RAG the model invents defaults and parameter names with confidence (1/10).
- RAG answers were also *faster*: short cited answers instead of long invented ones.
- v1 failures were retrieval misses: the right section, but the chunk with the parameter list was not in the top 4.
- Smaller chunks alone changed nothing (6/10). Hybrid keyword scoring added +2: questions contain exact identifiers
  (`lagThreshold`, `mode`, `protocol`) that embeddings match poorly.
- Remaining 2 failures are model reasoning, not retrieval: it inferred "default protocol = HTTP" from the examples (docs say `auto`),
  and listed RabbitMQ modes incompletely.
- Next experiments: ozai-think on the failures; a reranker; a larger model on GPU (article 3).

Correction (2026-11-10): the 2 remaining failures are RETRIEVAL misses, not model reasoning.
- Checked the top-6 chunks for both RabbitMQ questions: all are example YAML sections ("HTTP protocol (with `MessageRate` ...)",
  "AMQP protocol"). The chunks that state the answer (trigger spec: `protocol ... Default value is auto`, `mode` with all 5 values,
  parameter list: `default: auto`) were never retrieved. The model inferred "default = HTTP" from what it was shown.
- ozai-think on the same 2 questions (RAG_MAX_TOKENS=4000): still wrong, and slower (27 s / 41 s vs 17 s / 21 s for ozai).
  Thinking cannot recover facts that are not in the context.
- Also: the doc lists 5 modes (QueueLength, MessageRate, DeliverGetRate, PublishedToDeliveredRatio, ExpectedQueueConsumptionTime);
  the eval only requires 3 of them.

v3 — MMR (2026-11-10)
- Root cause of both misses: the RabbitMQ page has 11 near-identical YAML example sections; they all contain "mode"/"protocol",
  so they filled all 6 slots. The answer chunks (Trigger Specification) ranked 14-30.
- top-k 12 (no MMR) recovered 1 of 2. MMR λ=0.7 over the top 30 recovered the `mode` chunk with the same 6-chunk budget:
  answer now lists all 5 modes. No regressions on the other 9 questions → 9/10.
- Still wrong: RabbitMQ default protocol. The retrieved spec chunk is the wrong third of that section; the one with
  "Default value is `auto`" is still not retrieved (tried MMR 0.5-0.7, k 6-8). Stopped tuning there: 10 questions are too few
  to keep tuning against without overfitting. Next: a reranker or structure-aware chunking (one chunk per parameter).
- ozai-think on that question (with MMR): still wrong (says AMQP), 80 s, but states "the context does not explicitly state the
  default, so it is inferred". Better calibrated, not more correct.
