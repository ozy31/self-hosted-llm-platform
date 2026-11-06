# 03 — Observability: Grafana on LiteLLM spend logs (2026-11-02)

- LiteLLM's Prometheus callback is an Enterprise feature: with callbacks: ["prometheus"] the OSS image exposed no litellm_* metrics.
- Instead: LiteLLM already writes every request to Postgres ("LiteLLM_SpendLogs": startTime, completionStartTime, endTime, request_duration_ms, tokens, key alias in metadata, status).
- Grafana 11.3 → Postgres datasource with a read-only role (grafana_ro, SELECT on that one table only). Dashboard provisioned as code: grafana/dashboards/ozai-gateway.json.
- Panels: requests, errors, completion tokens, TTFT p95 · requests by API key · TTFT p50/p95 · end-to-end latency p50/p95 · per-request decode tok/s · tokens by model.
- TTFT = completionStartTime - startTime; decode speed = completion_tokens / (endTime - completionStartTime).
- Gotcha: Grafana provisioning YAML — `$__env{...}` inside a flow mapping `{ }` breaks parsing; use block style and plain $VAR.
- Trade-off vs Prometheus: SQL over request logs = exact per-request percentiles, but no GPU/queue-depth metrics (Ollama exposes none). On EKS/vLLM (article 3) vLLM's native /metrics + DCGM cover that.
- Bug found 2026-11-06: non-streaming requests log completionStartTime ≈ endTime (decode time 0.000 s) → decode panel spiked to ~13k tok/s and their "TTFT" was really full latency. Fix: TTFT/decode queries only count rows with endTime - completionStartTime > 100 ms (streamed). Also: stat colors (TTFT p95 thresholds 2 s/5 s), timeseries interval 10s, NULL gap fill.
