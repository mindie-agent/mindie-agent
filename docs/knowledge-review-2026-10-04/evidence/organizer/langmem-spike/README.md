# LangMem 0.0.30 isolated interface spike

Completed 2026-10-04, 08:52:29–08:55:09 UTC. All messages and model outputs are synthetic. No real model, provider client, private history, database, publication or product source was used. This establishes interface and scheduling behavior, **not summary quality, real token usage or cost**.

## Reproduction

An isolated `/tmp` virtual environment was created with `uv venv ... --python python3`; uv selected CPython **3.13.12**. The existing user Python environment was not changed. `langmem==0.0.30` resolved successfully to 50 distributions. `resolved-requirements.txt` records every resolved version; it is a version snapshot, not a hashes-verified multi-platform lock.

```sh
uv venv /tmp/mindie-framework-audit-20261004/langmem-spike-venv --python 3.13.12
uv pip install --python /tmp/mindie-framework-audit-20261004/langmem-spike-venv/bin/python -r resolved-requirements.txt
PYTHONDONTWRITEBYTECODE=1 LANGSMITH_TRACING=false \
  /tmp/mindie-framework-audit-20261004/langmem-spike-venv/bin/python spike.py
```

Run the last two commands from this evidence directory. No credentials are needed. The script uses only `.invoke(messages)` returning a constructed `AIMessage`, so it also establishes that this function does not require a LangGraph graph, BaseStore, database or provider SDK client instance. Those packages are nevertheless installation dependencies of the published LangMem distribution.

## Observed mechanisms

`results.json` is the final run; `first-run-results.json` preserves the first run before adding the title/summary bridge case. Every case asserts its result. The deterministic counter measures **characters**, not model tokens; these budgets are solely a way to trigger library branches.

- Below threshold: zero model calls. Two complete batches: one call each. The second prompt contains the old summary and the second batch, without the first batch's raw text. Both delta-only and cumulative-history forms were exercised.
- RunningSummary survives deterministic JSON serialization and reconstruction; no database is required by the library. The caller still needs atomic persistence with its own coverage cursor and attempt ledger.
- Over-budget case: only message `oversized-3` reaches the fake model, while IDs `oversized-0` through `oversized-3` are all recorded as summarized. This reproduces the trimming/coverage mismatch and is why integration must supply complete, bounded batches with prompt/output headroom.
- `max_summary_tokens=64` accepts a fake 200-character summary. It is a budget parameter; the real Harness transport must enforce actual output limits.
- A fake provider error propagates after one invoke. This function does not retry it.
- Custom `initial_summary_prompt` and `existing_summary_prompt` allow the same invocation to return a JSON string containing `title` and `summary`. The second prompt includes the previous JSON; deterministic parsing maps it back into metadata. There is no required second model call. The fake returned valid JSON by construction, so real Harness output-schema enforcement remains untested here.

## Dependency and process observations

Published package: LangMem 0.0.30, MIT. Installed summarization module SHA-256: `53b6cabcf3a64fc9445cb5a2252e8e8ab67de9a726ab04bca5aa1cd35bdd0909`.

- 50 resolved distributions, including LangMem, versus its eight direct dependencies.
- Site-packages apparent file bytes after import: 46,534,493 (44.38 MiB).
- `du -sk` for the venv: 61,740 KiB (60.29 MiB). Filesystem allocation is different from apparent file size. Neither number includes the shared Python installation or uv's download cache.
- First process import: 5.306 seconds; peak RSS: 97,140,736 bytes (92.64 MiB). This is one local cold-ish observation, not a representative benchmark. The final rerun was faster; inspect its JSON rather than extrapolating either sample.

## Integration implication

It is feasible to reuse `summarize_messages` and `RunningSummary` through the current Harness boundary. Configure custom prompts, pass a single model adapter that keeps the current output schema and process limits, parse the JSON result deterministically, and persist the returned state in the existing database. The library can replace the summary-selection/state algorithm; authorization, redaction, transaction boundaries, model-attempt accounting and publication remain domain responsibilities. The complete body stays separate from this fallible, rebuildable reference index.
