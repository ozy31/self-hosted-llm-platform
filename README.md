# self-hosted-llm-platform

Self-hosted LLM platform ("OzAI"): open-weight models served behind an OpenAI-compatible
gateway with per-user keys, model access control, rate limits and usage tracking.

Work in progress. Built step by step, with measured numbers at each step.

## Stack

| Layer | Component |
|---|---|
| Inference | Ollama on macOS (Metal GPU): `qwen3:8b`, `qwen2.5-coder:3b` |
| Gateway | LiteLLM (OpenAI-compatible API, virtual keys, RPM limits, spend in Postgres) |
| UI | Open WebUI, talking to the gateway only; web search via self-hosted SearXNG |
| Observability | Grafana on LiteLLM request logs (read-only Postgres role) |
| IDE | VS Code + Continue: chat via gateway, autocomplete (FIM) direct to Ollama |

Models exposed through the gateway: `ozai` (Qwen3 8B, thinking off), `ozai-think`, `ozai-coder`.

## Run

```bash
cp .env.example .env   # fill in random secrets
cp searxng/settings.yml.example searxng/settings.yml   # set secret_key
ollama serve           # native, for GPU access
docker compose up -d   # postgres, litellm :4000, open-webui :3000, grafana :3001, searxng :8888 (127.0.0.1 only)
```

Grafana reads LiteLLM's request log through a read-only role:

```sql
CREATE ROLE grafana_ro LOGIN PASSWORD '<GRAFANA_DB_PASSWORD>';
GRANT CONNECT ON DATABASE litellm TO grafana_ro;
GRANT USAGE ON SCHEMA public TO grafana_ro;
GRANT SELECT ON "LiteLLM_SpendLogs" TO grafana_ro;
```

## Roadmap

- [x] 1. Local inference benchmark ([benchmarks/01](benchmarks/01-local-ollama.md))
- [x] 2. Gateway + UI with per-key auth, model allow-lists and rate limits
- [x] Concurrency test ([benchmarks/02](benchmarks/02-concurrency-ollama-default.md))
- [ ] 3. Cloudflare Tunnel + Access for external users
- [x] 4. Grafana: TTFT, latency p50/p95, tokens/s, usage per key ([notes/03](notes/03-observability.md))
- [x] 5. Load test: 1–8 concurrent users ([loadtest/bench.py](loadtest/bench.py))
- [x] 6. RAG: web search via SearXNG; document RAG with hybrid retrieval + MMR, 1/10 → 9/10 on a KEDA eval ([benchmarks/03](benchmarks/03-rag-eval.md))
- [ ] 7. vLLM on EKS with GPU autoscaling ([terraform-aws-eks-ai-cluster](https://github.com/ozy31/terraform-aws-eks-ai-cluster)), cost per 1M tokens vs local

## Document RAG

```bash
# fetch docs into rag/docs/keda (not committed), e.g. KEDA 2.22 scaler pages from github.com/kedacore/keda-docs
ollama pull nomic-embed-text
python3 rag/ozai_rag.py ingest rag/docs/keda
RAG_KEY=sk-... python3 rag/ozai_rag.py ask "Which SASL modes does the Kafka scaler support?"
RAG_KEY=sk-... python3 rag/ozai_rag.py eval rag/eval_keda.json
```
