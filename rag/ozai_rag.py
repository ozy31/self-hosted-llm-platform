"""Minimal RAG for OzAI: chunk Markdown docs, embed with Ollama, retrieve by cosine similarity,
answer through the LiteLLM gateway. Standard library only.

Usage:
  python3 rag/ozai_rag.py ingest rag/docs/keda            # build rag/index.json
  python3 rag/ozai_rag.py ask "How does the RabbitMQ scaler pick a mode?"
  python3 rag/ozai_rag.py eval rag/eval_keda.json          # baseline vs RAG accuracy

Env: RAG_KEY (LiteLLM virtual key), optional RAG_MODEL (default ozai), RAG_MAX_TOKENS (default 400;
raise it for ozai-think, which spends tokens on reasoning first).
"""
import json, math, os, re, sys, time, urllib.request
from pathlib import Path

OLLAMA = "http://localhost:11434"
GATEWAY = "http://localhost:4000/v1/chat/completions"
EMBED_MODEL = "nomic-embed-text"
INDEX = Path(__file__).with_name("index.json")
CHUNK_WORDS = int(os.environ.get("RAG_CHUNK_WORDS", 150))
OVERLAP_WORDS = CHUNK_WORDS // 6
TOP_K = int(os.environ.get("RAG_TOP_K", 6))
# Weight of the keyword score in hybrid retrieval; 0 = pure embeddings.
HYBRID = float(os.environ.get("RAG_HYBRID", 0.3))
# MMR diversity: 1 = pure relevance (off); lower values penalise chunks similar to ones already picked.
MMR = float(os.environ.get("RAG_MMR", 0.7))
STOPWORDS = set("what which does the and for are with that this from how its into does keda scaler value values "
                "default possible parameter parameters use uses let you one".split())

SYSTEM = ("Answer the question using only the numbered context below. Cite sources like [1]. "
          "If the answer is not in the context, say you don't know.")


def post(url, body, headers=None, timeout=300):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def embed(texts, kind):
    # nomic-embed-text expects task prefixes; documents and queries use different ones.
    prefix = "search_document: " if kind == "doc" else "search_query: "
    out = []
    for i in range(0, len(texts), 32):
        out += post(f"{OLLAMA}/api/embed", {"model": EMBED_MODEL, "input": [prefix + t for t in texts[i:i + 32]]})["embeddings"]
    return out


def chunk_markdown(path):
    text = path.read_text()
    text = re.sub(r"\A(\+\+\+|---)\n.*?\n\1\n", "", text, flags=re.S)  # front matter
    title, sections, heading, buf = path.stem, [], "", []
    for line in text.splitlines():
        if line.startswith("#"):
            if buf: sections.append((heading, buf))
            heading, buf = line.lstrip("# ").strip(), []
        else:
            buf.append(line)
    if buf: sections.append((heading, buf))
    chunks = []
    for heading, lines in sections:
        words = " ".join(lines).split()
        step = CHUNK_WORDS - OVERLAP_WORDS
        for start in range(0, max(len(words), 1), step):
            piece = " ".join(words[start:start + CHUNK_WORDS])
            if len(piece.split()) < 20: continue
            # Keep the file and heading in the chunk: "default: 10" is useless without knowing which scaler it belongs to.
            chunks.append({"source": f"{title} > {heading}" if heading else title, "text": f"[{title} > {heading}] {piece}"})
            if start + CHUNK_WORDS >= len(words): break
    return chunks


def ingest(folder):
    chunks = [c for p in sorted(Path(folder).glob("*.md")) for c in chunk_markdown(p)]
    t = time.time()
    for c, v in zip(chunks, embed([c["text"] for c in chunks], "doc")):
        c["vec"] = v
    INDEX.write_text(json.dumps(chunks))
    print(f"indexed {len(chunks)} chunks from {folder} in {time.time() - t:.1f}s -> {INDEX}")


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def keyword_scores(question, chunks):
    # IDF-weighted share of the question's terms found in each chunk. Embeddings are weak on exact
    # identifiers like `lagThreshold`; this catches them.
    terms = {t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", question)} - STOPWORDS
    texts = [c["text"].lower() for c in chunks]
    idf = {t: math.log(len(texts) / (1 + sum(t in x for x in texts))) + 1 for t in terms}
    total = sum(idf.values()) or 1
    return [sum(w for t, w in idf.items() if t in x) / total for x in texts]


def retrieve(question, k=TOP_K):
    chunks, q = json.loads(INDEX.read_text()), embed([question], "query")[0]
    kw = keyword_scores(question, chunks) if HYBRID else [0] * len(chunks)
    scored = sorted([(cosine(q, c["vec"]) + HYBRID * s, c) for c, s in zip(chunks, kw)], key=lambda x: x[0], reverse=True)
    if MMR >= 1:
        return [c for _, c in scored[:k]]
    # Maximal Marginal Relevance: near-identical chunks (e.g. ten YAML examples of the same scaler)
    # otherwise fill every slot and push out the one paragraph that states the answer.
    pool, picked = scored[:5 * k], []
    while pool and len(picked) < k:
        best = max(pool, key=lambda x: MMR * x[0] - (1 - MMR) * max((cosine(x[1]["vec"], p["vec"]) for p in picked), default=0))
        picked.append(best[1]); pool.remove(best)
    return picked


def chat(messages):
    body = {"model": os.environ.get("RAG_MODEL", "ozai"), "messages": messages, "temperature": 0,
            "max_tokens": int(os.environ.get("RAG_MAX_TOKENS", 400))}
    d = post(GATEWAY, body, {"Authorization": f"Bearer {os.environ['RAG_KEY']}"})
    return d["choices"][0]["message"]["content"].strip(), d["usage"]["prompt_tokens"]


def ask(question, use_rag=True):
    if not use_rag:
        return chat([{"role": "user", "content": question}]) + ([],)
    hits = retrieve(question)
    context = "\n\n".join(f"[{i + 1}] {h['text']}" for i, h in enumerate(hits))
    answer, tokens = chat([{"role": "system", "content": f"{SYSTEM}\n\n{context}"}, {"role": "user", "content": question}])
    return answer, tokens, [h["source"] for h in hits]


def score(answer, expect):
    # Every expected pattern must appear; crude, but objective and repeatable.
    return all(re.search(p, answer, re.I) for p in expect)


def evaluate(path):
    cases = json.loads(Path(path).read_text())
    rows, totals = [], {"base": 0, "rag": 0}
    for i, c in enumerate(cases, 1):
        row = {"q": c["q"]}
        for mode in ("base", "rag"):
            t = time.time()
            answer, tokens, _ = ask(c["q"], use_rag=(mode == "rag"))
            ok = score(answer, c["expect"])
            totals[mode] += ok
            row[mode] = (ok, time.time() - t, tokens)
            row[mode + "_answer"] = answer
        rows.append(row)
        print(f"{i:2}. base {'✅' if row['base'][0] else '❌'}  rag {'✅' if row['rag'][0] else '❌'}  {c['q'][:70]}", flush=True)
    n = len(cases)
    avg = lambda m, j: sum(r[m][j] for r in rows) / n
    print(f"\nAccuracy  baseline {totals['base']}/{n}   RAG {totals['rag']}/{n}")
    print(f"Avg latency  baseline {avg('base', 1):.1f}s   RAG {avg('rag', 1):.1f}s")
    print(f"Avg prompt tokens  baseline {avg('base', 2):.0f}   RAG {avg('rag', 2):.0f}")
    Path(__file__).with_name("eval_results.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "ingest": ingest(sys.argv[2])
    elif cmd == "ask":
        answer, tokens, sources = ask(sys.argv[2])
        print(answer, "\n\nSources:", *sources, sep="\n")
    elif cmd == "eval": evaluate(sys.argv[2])
