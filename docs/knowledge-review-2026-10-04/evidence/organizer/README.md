# Organizer synthetic audit evidence

Audited on 2026-10-04. These are dirty local candidate trees, not deployment evidence.

- knowledge HEAD: `6a9fb51d41f9787122ef61cbdf81df981d12cded` (9 tracked modifications, 2 untracked source/test files).
- codex HEAD: `56f28c39e68f4435c03a007c9906aa7c92ed85ae` (5 tracked modifications).
- `results.json` records SHA-256 of every implementation file relevant to the probes.
- Python 3.11.13; pytest 9.1.1; `/opt/homebrew/bin/gitleaks` reports 8.30.1.
- No external model, real session, publication, product source edit, or deployment was performed.

Run from the initial `knowledge/` research checkout. Set `KNOWLEDGE_RESEARCH_ROOT` and `CODEX_RESEARCH_ROOT` to the sibling checkouts recorded by commit and source hashes; `ARCHITECTURE_ROOT` identifies this documentation checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$KNOWLEDGE_RESEARCH_ROOT:$KNOWLEDGE_RESEARCH_ROOT/tests" \
python3 "$ARCHITECTURE_ROOT/docs/knowledge-review-2026-10-04/evidence/organizer/probes.py"
```

The script imports repository fixtures, which create an isolated temporary HOME and disable diagnostic reporting. Its only native children are the local scanner and synthetic Python workers. Worker calls in the returned JSON are simulated call counts, not actual model usage.

Relevant regression suite run:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$KNOWLEDGE_RESEARCH_ROOT" \
python3 -m pytest -p no:cacheprovider -q tests/test_summary_input.py tests/test_public_transcript.py tests/test_history_import.py tests/test_diagnostic_snapshot.py
```

Result: **106 passed in 73.62s**. The suite's scanner installer uses its isolated test cache.

From the initial `codex/` research checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$KNOWLEDGE_RESEARCH_ROOT:$CODEX_RESEARCH_ROOT/plugins/mindie-agent/scripts" \
python3 -m unittest discover -s tests -p 'test_organizer*.py' -v
```

Result: **18 passed in 0.599s**.

Interpretation: the tests establish local component behavior, not native hook activation, Luna summary quality, actual token charges, GitHub publication, or semantic confidentiality. The cross-capture probe demonstrates secret-fragment text in saved body and simulated worker input. The current outgoing scanner separately rejects a redaction placeholder; no actual data was published.

Public-evidence preparation replaced machine-specific checkout paths with workspace roles. The probe now derives the sibling checkout root from the documented working directory. These path-only changes were syntax-checked, not rerun; the recorded initial measurements and exercised product-source hashes remain unchanged.
