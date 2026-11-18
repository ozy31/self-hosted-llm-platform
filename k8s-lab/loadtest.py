"""Step-load test for the kind lab: N users loop requests per phase; replicas and queue sampled every 2s.

Usage: python3 k8s-lab/loadtest.py <out.json> [phases, e.g. 60:1,240:8,180:1]
"""
import json, subprocess, sys, threading, time, urllib.parse, urllib.request

URL = "http://localhost:8081/v1/chat/completions"
PROM = "http://localhost:9090/api/v1/query"
PROMPT = "Explain how Kubernetes Horizontal Pod Autoscaler works."
MAX_TOKENS = 128
CTX = "kind-ozai-lab"


def one_request(phase):
    body = json.dumps({"model": "ozai-lab", "stream": True, "max_tokens": MAX_TOKENS,
                       "stream_options": {"include_usage": True},
                       "messages": [{"role": "user", "content": PROMPT}]}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    t0 = time.time(); start = time.perf_counter(); ttft = None; tokens = 0
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
        return {"t": t0, "phase": phase, "ttft": ttft, "total": time.perf_counter() - start, "tokens": tokens}
    except Exception as e:
        return {"t": t0, "phase": phase, "error": str(e)}


def prom(q):
    try:
        with urllib.request.urlopen(PROM + "?query=" + urllib.parse.quote(q), timeout=3) as r:
            res = json.load(r)["data"]["result"]
            return float(res[0]["value"][1]) if res else 0.0
    except Exception:
        return None


def sampler(stop, samples):
    while not stop.is_set():
        out = subprocess.run(["kubectl", "--context", CTX, "-n", "ozai", "get", "deploy", "ozai-lab",
                              "-o", "jsonpath={.spec.replicas} {.status.readyReplicas}"],
                             capture_output=True, text=True).stdout.split()
        samples.append({"t": time.time(), "desired": int(out[0]) if out else None,
                        "ready": int(out[1]) if len(out) > 1 else 0,
                        "deferred": prom('sum(llamacpp:requests_deferred{namespace="ozai"})'),
                        "processing": prom('sum(llamacpp:requests_processing{namespace="ozai"})')})
        time.sleep(2)


def main():
    out_path = sys.argv[1]
    phases = [tuple(int(x) for x in p.split(":")) for p in (sys.argv[2] if len(sys.argv) > 2 else "60:1,240:8,180:1").split(",")]
    results, samples, stop = [], [], threading.Event()
    threading.Thread(target=sampler, args=(stop, samples), daemon=True).start()
    t_start = time.time()
    for i, (secs, users) in enumerate(phases):
        end = time.time() + secs
        def user():
            while time.time() < end:
                results.append(one_request(i))
        ts = [threading.Thread(target=user) for _ in range(users)]
        print(f"phase {i}: {users} users for {secs}s", flush=True)
        for t in ts: t.start()
        for t in ts: t.join()
    stop.set(); time.sleep(2)
    json.dump({"start": t_start, "phases": phases, "requests": results, "samples": samples}, open(out_path, "w"), indent=1)
    ok = [r for r in results if "error" not in r and r["ttft"] is not None]
    for i, (secs, users) in enumerate(phases):
        p = sorted(r["ttft"] for r in ok if r["phase"] == i)
        if p:
            print(f"phase {i} ({users}u): n={len(p)} ttft p50={p[len(p)//2]:.2f}s p95={p[int(len(p)*.95)-1]:.2f}s")
    print("errors:", sum(1 for r in results if "error" in r), " max ready:", max((s["ready"] or 0) for s in samples))


if __name__ == "__main__":
    main()
