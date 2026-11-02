# 02 — Gateway: Ollama + LiteLLM + Open WebUI (2026-10-31)

Architecture
- Ollama native on macOS (Metal GPU). Docker on Mac has no GPU passthrough → Ollama in a container would be CPU-only.
- docker compose: postgres (LiteLLM keys/spend) · litellm :4000 (OpenAI-compatible) · open-webui :3000. All bound to 127.0.0.1 until step 3 (Cloudflare Tunnel).
- Containers reach Ollama via host.docker.internal:11434.

Verified
- No key → 401. Friend key restricted to qwen3-8b; asking for qwen2.5-coder-3b → 403.
- rpm_limit=10: 12 rapid requests → 9×200 then 429 (one earlier request already counted in the window).
- Per-key usage recorded (prompt/completion tokens) in Postgres.

Gotchas (article material)
- max_budget=0 on a key blocks everything ("Budget has been exceeded… 0.0/0.0") — local models cost $0, so leave budget unset or set a custom per-token price.
- qwen3 is a thinking model: with a small max_tokens the whole budget goes to <think> and the answer comes back empty. Use reasoning_effort "none" (or raise max_tokens).
