#!/usr/bin/env python3
"""bench.py — tiny OpenRouter free-tier benchmark. Stdlib only.

Usage: python3 bench.py [runs]     (default runs=2)
       python3 bench.py --selftest

Reads OPENROUTER_API_KEY from env or .env. Writes results.csv, prints a table.
"""
import csv, json, os, re, sys, time, urllib.request, urllib.error

URL = "https://openrouter.ai/api/v1/chat/completions"

# ponytail: free-tier ids drift over time; stale id just shows as an error row, fix MODELS then.
MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "qwen/qwen3.8-27b:free",
    "poolside/laguna-s-2.1:free",
]


def check_prime(text):
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    code = m.group(1) if m else text
    ns = {}
    try:
        exec(code, ns)  # ponytail: exec of model output, fine for local eval of known models
        f = ns.get("is_prime")
        return bool(f) and f(2) and f(97) and not f(1) and not f(91) and not f(561)
    except Exception:
        return False


def check_json_list(text):
    try:
        v = json.loads(re.search(r"\[.*\]", text, re.S).group(0))
        return isinstance(v, list) and len(v) == 3 and all(isinstance(x, str) for x in v)
    except Exception:
        return False


# (id, prompt, check) — check=None means unscored (eyeball in CSV).
PROMPTS = [
    ("qa",       "What is the capital of France? Reply with just the city name.",
                 lambda t: t.strip().strip(".").lower() == "paris"),
    ("math",     "What is 17*23? Reply with just the number.",
                 lambda t: "391" in t),
    ("reason",   "A bat and a ball cost $1.10 total. The bat costs $1 more than the ball. "
                 "How many cents does the ball cost? Reply with just the number.",
                 lambda t: bool(re.search(r"\b5\b", t)) and "10" not in t),
    ("json",     "List three colors as a JSON array of strings. Reply with only the JSON.",
                 check_json_list),
    ("code",     "Write a Python function is_prime(n) -> bool. Reply with only the code.",
                 check_prime),
    ("summary",  "In one sentence, summarize: Photosynthesis is the process by which green plants "
                 "use sunlight, water and carbon dioxide to make glucose and release oxygen.",
                 lambda t: "light" in t.lower() and len(t) < 400),
]


def load_key():
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    try:
        for line in open(".env"):
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    except FileNotFoundError:
        pass
    sys.exit("Set OPENROUTER_API_KEY in env or .env")


def parse_chunk(line):
    """One SSE line -> (delta_text, usage_dict|None). None line -> (None, None)."""
    if not line.startswith("data:"):
        return None, None
    data = line[5:].strip()
    if data == "[DONE]":
        return None, "DONE"
    chunk = json.loads(data)
    text = None
    if chunk.get("choices"):
        text = chunk["choices"][0].get("delta", {}).get("content")
    return text, chunk.get("usage")


def run_one(model, prompt):
    """Returns dict of metrics; 'error' set on failure."""
    body = json.dumps({
        "model": model, "stream": True, "usage": {"include": True},
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {load_key()}", "Content-Type": "application/json"})
    t0 = time.time()
    ttft, parts, usage = None, [], {}
    with urllib.request.urlopen(req, timeout=180) as r:
        for raw in r:
            text, usg = parse_chunk(raw.decode("utf-8", "replace").strip())
            if usg == "DONE":
                break
            if text:
                if ttft is None:
                    ttft = time.time() - t0
                parts.append(text)
            if isinstance(usg, dict):
                usage = usg
    total = time.time() - t0
    text = "".join(parts)
    ctoks = usage.get("completion_tokens") or max(1, len(text) // 4)  # ponytail: rough fallback
    return {"ttft": ttft or total, "total": total, "ctoks": ctoks,
            "tps": ctoks / total if total else 0, "text": text}


def run_call(model, prompt, retries=1):
    for attempt in range(retries + 1):
        try:
            return run_one(model, prompt)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(20)
                continue
            return {"error": f"HTTP {e.code}"}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}


def selftest():
    assert parse_chunk('data: {"choices":[{"delta":{"content":"hi"}}]}') == ("hi", None)
    assert parse_chunk('data: {"choices":[],"usage":{"completion_tokens":3}}') == (None, {"completion_tokens": 3})
    assert parse_chunk("data: [DONE]") == (None, "DONE")
    assert parse_chunk(": ping") == (None, None)
    assert check_prime("```python\ndef is_prime(n):\n    return n > 1 and all(n % i for i in range(2, n))\n```")
    assert not check_prime("def is_prime(n):\n    return True")
    assert check_json_list('["red", "green", "blue"]')
    assert not check_json_list('["red", "green"]')
    pid_ok = {p[0]: p[2]("Paris") for p in PROMPTS if p[0] == "qa"}
    assert pid_ok["qa"]
    print("selftest ok")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    runs = int(next((a for a in sys.argv[1:] if a.isdigit()), 2))
    models = sys.argv[sys.argv.index("-m") + 1].split(",") if "-m" in sys.argv else MODELS
    rows = []
    for model in models:
        for pid, prompt, check in PROMPTS:
            for r in range(runs):
                res = run_call(model, prompt)
                row = {"model": model, "prompt": pid, "run": r,
                       "ttft_s": "", "total_s": "", "ctoks": "", "tok_s": "",
                       "pass": "", "error": res.get("error", "")}
                if "error" not in res:
                    ok = check(res["text"]) if check else None
                    row.update(ttft_s=f"{res['ttft']:.2f}", total_s=f"{res['total']:.2f}",
                               ctoks=res["ctoks"], tok_s=f"{res['tps']:.1f}",
                               pass_="" if ok is None else ("1" if ok else "0"))
                    row["pass"] = row.pop("pass_")
                rows.append(row)
                status = row["error"] or f"{row['tok_s']} tok/s pass={row['pass']}"
                print(f"{model.split('/')[1][:28]:30} {pid:8} r{r}  {status}", flush=True)
                time.sleep(1)  # ponytail: be nice to free-tier rate limits
    cols = ["model", "prompt", "run", "ttft_s", "total_s", "ctoks", "tok_s", "pass", "error"]
    with open("results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)

    print("\n== summary (medians over successful calls) ==")
    print(f"{'model':32} {'pass%':>6} {'ttft_s':>8} {'total_s':>8} {'tok/s':>7} {'errors':>6}")
    for m in models:
        mine = [r for r in rows if r["model"] == m]
        good = [r for r in mine if not r["error"]]
        errs = len(mine) - len(good)
        scored = [int(r["pass"]) for r in good if r["pass"] != ""]
        def med(key):
            vals = sorted(float(r[key]) for r in good)
            return vals[len(vals) // 2] if vals else 0
        print(f"{m.split('/')[1][:30]:32} "
              f"{(100 * sum(scored) / len(scored)) if scored else 0:5.0f}% "
              f"{med('ttft_s'):8.2f} {med('total_s'):8.2f} {med('tok_s'):7.1f} {errs:6}")
    print("\nwrote results.csv")


if __name__ == "__main__":
    main()
