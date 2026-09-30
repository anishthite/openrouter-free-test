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
| **openrouter/free** (router) | **100%** | 1.8s | 44 | **0** |
| nvidia/nemotron-3-ultra-550b:free | 100% | 1.6s | 37 | 0 |
| nvidia/nemotron-3-super-120b:free | 83% | 1.2s | 43 | 0 |
| qwen/qwen3.8-27b:free | 100%* | 1.6s | 48 | 7× 429 |
| poolside/laguna-s-2.1:free | 100% | 6.8s | 34 | 0 |
| google/gemma-4-31b-it:free | — | — | — | 12× 429 |

\* when not rate-limited. Takeaway: quality is there; per-model free-tier rate limits are the constraint. `openrouter/free` (the $0 router) matches the best individual model on quality/speed and had zero rate-limit failures — it's the default answer; pin a specific `:free` model only if you need determinism.

### 429 rates (12 calls/model)

| model | 429 rate |
|---|---|
| google/gemma-4-31b-it:free | 100% (12/12) |
| qwen/qwen3.8-27b:free | 58% (7/12) |
| nemotron ultra/super, laguna, openrouter/free | 0% |
| **all calls** | **26% (19/72)** |

Rate limits are per-model, not tier-wide: gemma was dead in practice, qwen a coin flip, everything else clean. Small sample; limits are rolling per-model windows so rates vary by hour.
