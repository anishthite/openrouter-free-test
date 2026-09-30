# openrouter-free-test

Tiny stdlib-only benchmark for OpenRouter free-tier models: quality + speed.

```
echo "OPENROUTER_API_KEY=sk-or-..." > .env
python3 bench.py        # 2 runs/prompt; pass N for more
python3 bench.py --selftest
```

Scored prompts: QA, math, reasoning trap, JSON format, codegen (exec'd), summary. Metrics: TTFT, latency, tok/s, pass rate, errors → stdout table + `results.csv`.

## 2026-09-29 results

| model | pass% | TTFT | tok/s | errors |
|---|---|---|---|---|
| nvidia/nemotron-3-ultra-550b:free | 100% | 1.6s | 37 | 0 |
| nvidia/nemotron-3-super-120b:free | 83% | 1.2s | 43 | 0 |
| qwen/qwen3.8-27b:free | 100%* | 1.6s | 48 | 7× 429 |
| poolside/laguna-s-2.1:free | 100% | 6.8s | 34 | 0 |
| google/gemma-4-31b-it:free | — | — | — | 12× 429 |

\* when not rate-limited. Takeaway: quality is there; per-model free-tier rate limits are the constraint.
