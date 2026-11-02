"""Concurrency benchmark for the OzAI gateway: TTFT, end-to-end latency and tokens/s per level.

Usage: python3 loadtest/bench.py <api_key> [levels, e.g. 1,2,4,8] [model]
"""
import json, statistics, sys, threading, time, urllib.request

URL = "http://localhost:4000/v1/chat/completions"
PROMPT = "Explain how Kubernetes Horizontal Pod Autoscaler works."
MAX_TOKENS = 128


def one_request(key, model, out):
    body = json.dumps({"model": model, "stream": True, "max_tokens": MAX_TOKENS,
                       "stream_options": {"include_usage": True},
                       "messages": [{"role": "user", "content": PROMPT}]}).encode()
    req = urllib.request.Request(URL, body, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    start, ttft, tokens = time.perf_counter(), None, 0
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            for line in r:
                line = line.decode().strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                chunk = json.loads(line[6:])
                if chunk.get("usage"):
                    tokens = chunk["usage"].get("completion_tokens", tokens)
                if ttft is None and any(c.get("delta", {}).get("content") for c in chunk.get("choices", [])):
                    ttft = time.perf_counter() - start
        total = time.perf_counter() - start
        out.append({"ttft": ttft, "total": total, "tokens": tokens})
    except Exception as e:
        out.append({"error": str(e)})


def run_level(key, model, n):
    results = []
    threads = [threading.Thread(target=one_request, args=(key, model, results)) for _ in range(n)]
    t0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    wall = time.perf_counter() - t0
    ok = [r for r in results if "error" not in r]
    p = lambda xs, q: sorted(xs)[min(len(xs) - 1, int(q * len(xs)))]
    ttfts, totals = [r["ttft"] for r in ok if r["ttft"]], [r["total"] for r in ok]
    return {"users": n, "ok": len(ok), "errors": len(results) - len(ok),
            "ttft_p50": statistics.median(ttfts), "ttft_max": max(ttfts),
            "latency_p50": statistics.median(totals), "latency_max": p(totals, 1.0),
            "per_user_tok_s": statistics.median(r["tokens"] / r["total"] for r in ok),
            "total_tok_s": sum(r["tokens"] for r in ok) / wall}


if __name__ == "__main__":
    key = sys.argv[1]
    levels = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "1,2,4,8").split(",")]
    model = sys.argv[3] if len(sys.argv) > 3 else "ozai"
    print("| Users | OK/err | TTFT p50 | TTFT max | Latency p50 | Latency max | Per-user tok/s | Total tok/s |")
    print("|---|---|---|---|---|---|---|---|")
    for n in levels:
        r = run_level(key, model, n)
        print(f"| {r['users']} | {r['ok']}/{r['errors']} | {r['ttft_p50']:.1f}s | {r['ttft_max']:.1f}s | "
              f"{r['latency_p50']:.1f}s | {r['latency_max']:.1f}s | {r['per_user_tok_s']:.1f} | {r['total_tok_s']:.1f} |", flush=True)
