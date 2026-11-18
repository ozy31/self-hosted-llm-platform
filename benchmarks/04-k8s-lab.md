# 04 — Queue-depth autoscaling on a local kind cluster

Date: 2026-11-18. Everything local, no cloud resources.

## Setup

- kind v1.37 single node in Docker Desktop (8 vCPU, 8 GB), MacBook Pro M1 Pro.
- Inference: `ghcr.io/ggml-org/llama.cpp:server`, Qwen2.5-0.5B-Instruct Q4_K_M (CPU),
  `--parallel 2` (2 slots per pod), `--threads 2`, CPU request/limit 2. Weights mounted from the host.
- Prometheus (scrape every 5s) + KEDA 2.21, ScaledObject shaped like
  [terraform-aws-eks-ai-cluster](https://github.com/ozy31/terraform-aws-eks-ai-cluster)'s vLLM chart:
  min 1, max 3, scale up 1 pod / 15s, scale down 1 pod / 30s after 60s stabilization (shortened lab windows).
- Load: `k8s-lab/loadtest.py`, users loop streamed requests (128 max tokens):
  60s × 1 user → 240s × 8 users → 180s × 1 user.

Files: [k8s-lab/](../k8s-lab), raw results in [04-k8s-lab/](04-k8s-lab).

## Results (8-user phase)

| Run | Scaling metric | Requests done | Output tok/s | TTFT p50 | TTFT p95 | Errors |
|---|---|---|---|---|---|---|
| Baseline | none, 1 replica | 48 | 25.4 | 35.3 s | 35.6 s | 0 |
| KEDA A | waiting requests (`requests_deferred`), threshold 2 | 83 | 44.3 | 12.4 s | 36.5 s | 0 |
| KEDA B | in-flight (`processing + deferred`), threshold 2 = slots/pod | 97 | 51.7 | 4.7 s | 35.9 s | 0 |

Steady state only (requests started more than 60s after the 8-user phase began):

| Run | TTFT p50 | TTFT p95 |
|---|---|---|
| KEDA A | 12.4 s | 35.5 s |
| KEDA B | 0.95 s | 23.9 s |

1-user phases: TTFT 0.05 s, 22 tok/s per request in all runs.

## Timeline

| | KEDA A (waiting) | KEDA B (in-flight) |
|---|---|---|
| 2nd replica requested | ~17 s after load | ~11 s after load |
| 3rd replica requested | ~32 s | ~25 s |
| Pod ready after request | ~2 s (weights on local disk, 0.5B model) | ~2 s |
| Scale-down **during** full load | yes: 3 → 2 at ~137 s, back to 3 ~44 s later | no |
| Back to 1 replica after load | ~90 s | ~100 s |

## Findings

1. **Waiting-only metric flaps.** With 3 pods × 2 slots and 8 users, only 2 requests wait.
   KEDA computes `ceil(2 / 2) = 1` desired replica and scales down under full load. The metric falls
   *because* scaling worked. In-flight (processing + waiting) per slot does not have this feedback loop.
2. **Queued requests don't move.** Requests already queued inside a pod stay there when new pods
   arrive. Scale-up helps new requests; p95 TTFT barely changed in any run.
3. **maxReplicas is a capacity ceiling.** 8 users need 4 pods of 2 slots; max is 3, so 2 requests always wait.
4. **CPU batching gave almost no extra throughput:** 23.5 tok/s (1 request) vs 25.4 tok/s (2 slots busy);
   per-request speed halved (22 → 11 tok/s). GPU continuous batching behaves differently; these numbers
   say nothing about vLLM on a GPU.
5. KEDA warns that `cooldownPeriod` is ignored when `minReplicaCount >= 1`; the EKS chart sets
   `cooldownSeconds: 900` with `minReplicas: 1`, so that setting has no effect there.
