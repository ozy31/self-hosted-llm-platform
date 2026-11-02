# 01 — Local baseline (Ollama on Apple Silicon)

Date: 2026-10-31 · Hardware: MacBook M1 Pro, 16 GB unified memory · Ollama 0.32.15 (Metal, 100% GPU)
Prompt: "Explain Kubernetes autoscaling in 5 sentences." · max 200 tokens · thinking off · single request

| Model | Disk | RAM loaded | Cold load | Prompt eval | Generation |
|---|---|---|---|---|---|
| qwen2.5-coder:3b (Q4) | 1.9 GB | – | 2.1 s | 120 tok/s | 53.3 tok/s |
| qwen3:8b (Q4_K_M) | 5.2 GB | 5.6 GB | 3.9 s | 87 tok/s | 22.4 tok/s |

Notes
- Generation speed roughly halves going 3B → 8B: decoding is memory-bandwidth bound.
- 22 tok/s is comfortably faster than reading speed for one user; next step is to measure what happens under concurrency.
