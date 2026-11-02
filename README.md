# self-hosted-llm-platform

Self-hosted LLM platform ("OzAI"): open-weight models served behind an OpenAI-compatible
gateway with per-user keys, model access control, rate limits and usage tracking.

Work in progress. Built step by step, with measured numbers at each step.

## Stack

| Layer | Component |
|---|---|
| Inference | Ollama on macOS (Metal GPU): `qwen3:8b`, `qwen2.5-coder:3b` |
| Gateway | LiteLLM (OpenAI-compatible API, virtual keys, RPM limits, spend in Postgres) |
| UI | Open WebUI, talking to the gateway only |

Models exposed through the gateway: `ozai` (Qwen3 8B, thinking off), `ozai-think`, `ozai-coder`.

## Run

```bash
cp .env.example .env   # fill in random secrets
ollama serve           # native, for GPU access
docker compose up -d   # postgres, litellm :4000, open-webui :3000 (127.0.0.1 only)
```

## Roadmap

- [x] 1. Local inference benchmark ([benchmarks/01](benchmarks/01-local-ollama.md))
- [x] 2. Gateway + UI with per-key auth, model allow-lists and rate limits
- [x] Concurrency test ([benchmarks/02](benchmarks/02-concurrency-ollama-default.md))
- [ ] 3. Cloudflare Tunnel + Access for external users
- [ ] 4. Prometheus / Grafana: tokens/s, TTFT, queue depth
- [ ] 5. k6 load test
- [ ] 6. RAG
- [ ] 7. vLLM on EKS with GPU autoscaling ([terraform-aws-eks-ai-cluster](https://github.com/ozy31/terraform-aws-eks-ai-cluster)), cost per 1M tokens vs local
