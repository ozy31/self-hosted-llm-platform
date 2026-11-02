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

IDE integration (2026-11-02)
- VS Code + Continue: chat/edit → LiteLLM (model ozai, own key "vscode-continue"); autocomplete → Ollama directly (qwen2.5-coder:3b).
- Why: LiteLLM /v1/completions drops Ollama's FIM params (suffix, raw), so the coder model replies "Certainly! Here's…" instead of completing code. Ollama /api/generate with suffix does proper fill-in-the-middle. Tested both ways.
- Cursor: custom OpenAI base URL works only with a public URL (Cursor calls models from its own servers) → after Cloudflare step.

Open WebUI background tasks (2026-11-02)
- Open WebUI sends extra requests after every answer (title, tags, follow-up suggestions) to the SAME model by default → they queue in front of the user's next question on a single-GPU box.
- Fix: Admin > Settings > Interface: External Task Model = ozai-coder (3B), follow-ups + tags off. User-confirmed: answers start quickly again.

Silent context truncation (2026-11-02) — best bug of the project so far
- Symptom: web search enabled, but the model kept saying "I don't have access to live data".
- Gateway logs: every Open WebUI request had prompt_tokens = 2050 exactly, regardless of question.
- Repro: 5k-token prompt → prompt_tokens 2050; a word at the END was recalled, one at the START was lost → Ollama keeps the tail and drops the head, without any error.
- Open WebUI puts RAG/web-search context at the start → it was always cut off.
- Fix: num_ctx: 8192 on the LiteLLM model. Same test → prompt_tokens 5430, start-of-prompt word recalled. RAM 5.6 → 6.2 GB.
- Lesson: in LLM serving, "no error" doesn't mean "correct"; watch prompt token counts.
