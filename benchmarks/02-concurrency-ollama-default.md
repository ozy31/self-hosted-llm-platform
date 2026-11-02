| Users | OK/err | TTFT p50 | TTFT max | Latency p50 | Latency max | Per-user tok/s | Total tok/s |
|---|---|---|---|---|---|---|---|
| 1 | 1/0 | 0.5s | 0.5s | 7.0s | 7.0s | 18.4 | 18.4 |
| 2 | 2/0 | 57.7s | 60.8s | 63.8s | 66.9s | 2.0 | 3.8 |
| 4 | 4/0 | 16.1s | 25.3s | 22.2s | 31.5s | 5.9 | 16.3 |
| 8 | 8/0 | 21.7s | 43.1s | 27.8s | 49.1s | 4.7 | 20.9 |

Setup: M1 Pro 16 GB, Ollama 0.32.15 (OLLAMA_NUM_PARALLEL auto), model ozai = qwen3:8b Q4_K_M thinking off, 128 max tokens, via LiteLLM.

Observations (2026-11-01)
- Aggregate throughput is flat at ~16-21 tok/s no matter how many users: one GPU, decoding is memory-bandwidth bound. More users = same pie, smaller slices.
- TTFT goes from 0.5 s (1 user) to 20-40 s (4-8 users): requests queue.
- The 2-user row (58 s TTFT) is an outlier: the user was chatting in Open WebUI at the same time, and Open WebUI also sends background requests (title/tags/follow-ups) to the same model. To re-run on an idle machine.
