# Experience reuse evaluation

This directory separates deterministic evidence availability and resource
measurements from consumer task outcomes. Neither a query hit, fewer groups,
reachable references, nor a model's own rating proves successful reuse.

## Offline measurements

Use an existing Python environment containing the pinned knowledge dependencies.
The source root contains `knowledge`, `content`, `codex`, and `design` Git
checkouts. The scripts only read those repositories; stores and indices are
created under managed temporary directories. Results must be outside them.

```sh
python tools/reuse_evaluation/run_offline.py \
  --source-root /path/to/frozen-sibling-checkouts \
  --output /path/to/new-evaluation-output
```

The command makes no model call, network request, private transcript read, or
product-repository write. Its 120-second per-script test ceiling is an explicit
evaluation budget, not a MindIE product limit. A failed script stops the run and
is recorded with its error; partial output is not successful evaluation.

* `assess_public.py`: exact bytes, whitespace-normalized body identity, literal
  citations, and lexical candidate overlap. Similarity is not semantic identity.
* `assess_retrieval.py`: same-candidate citation-grouping ablation, response bytes,
  and actual one-block reads. There is no end-to-end consumer or model cost claim.
* `assess_projection.py`: full related metadata, anchor-only, and eight-field
  compact related previews from the same unprojected groups. The production
  cursor shape is used for full/compact; its digest is normalized to isolate
  serialization size. The anchor-only zero-offset cursor is an evaluation-only
  counterfactual. Expansion reuses the existing anchor envelope and does not
  replay the first two previews. Full bodies remain separate reads.

The projection fixtures intentionally place corrections at known ranks and
outside excerpts. They test loss of available evidence, not the frequency of
such cases or real retrieval recall.

## Paired consumer pilot: fixed before model execution

`consumer-cases.json` contains six synthetic local tasks: FP16 reference rounding,
changed device mapping, withdrawn speedup, a process-bound runtime failure, an
obsolete version-specific workaround, and an unrelated no-hit task. The visible
files and task prompt are identical within each pair. The corpus consists only
of the synthetic materials in that file. No private conversation is required.

Create two fresh workspaces and two independent consumer contexts per case.
Copy only `files` to each workspace. Supply the case `prompt` without an arm label,
expected answer, case category, evaluation narrative, or private grader. Both
arms use the same pinned model, effort, tool set, environment, initial files,
and business instructions. Record the resolved model/runtime identity before
running; if it cannot be established, report that uncertainty.

The baseline has no task-relevant knowledge available. The reuse arm may query
and read the frozen case materials through the normal query/read boundary; do
not paste all materials into its initial context. Use a disposable store per
case and disable capture/publication so earlier consumers cannot contaminate
later trials. Preserve the late correction in the complete speedup body.
The no-hit task returns no relevant material in both arms. If a runner instead
injects text or uses a mock retriever, label its result as that protocol and do
not call it an integrated MindIE test.

Randomize which arm runs first within each pair using a recorded seed. Keep
pairs independent, with no conversation/cache state deliberately transferred.
An assessor receives anonymous artifacts and business responses; the arm key
is disclosed only after grading. A model cannot be blinded to seeing a reference,
but it must not be told which result the experiment expects.

The pilot budget is 12 consumer runs, at most 8 consumer tool calls and 2,000
output tokens per run, with aggregate ceilings of 240,000 input tokens and
24,000 output tokens. A 300-second per-run test window may be selected before
the pilot starts. These are operator-selected experiment limits, never defaults
for normal business execution. Budget stops remain failed or censored outcomes;
do not replace them with a second attempt or drop the pair. Native usage fields
that are unavailable remain null. Do not estimate tokens from UTF-8 bytes.

Run the private oracle in a fresh evaluator process, outside the consumer's
workspace and only after the consumer finishes:

```sh
python tools/reuse_evaluation/grade_consumer.py \
  --case dtype_reference --workspace /path/to/completed-consumer-workspace
```

The grader checks produced code/configuration/analysis artifacts against fixed
rules. It is a local synthetic oracle, not an NPU runtime or hardware oracle.
Use an explicit evaluator timeout for generated code and record timeout/failure.
The evaluator must additionally grade the final business response against the
following rubric, without consulting the arm label:

| Criterion | Pass rule |
| --- | --- |
| Completed action | Private artifact oracle passes; claimed local validation actually ran. |
| Applicability | Current dtype, mapping, version and process boundary are respected. |
| Corrections | No withdrawn speedup or failed initial approach is repeated as a verified result. |
| Evidence status | Fixture/mock checks are not represented as hardware or native acceptance. |
| Uncertainty | Missing measurements remain unknown; no invented successful run. |
| User flow | No extra activation command, MindIE status instruction, diagnosis obligation or feedback request. |

Primary results are paired artifact completion and counts of harmful reuse,
unsupported claims, and extra user steps. Quality gates precede any resource
claim: zero harmful reuse or invented evidence, no new user steps, and no lower
completion in the observed pairs. Six cases are a pilot and do not establish a
population-wide effect or statistical significance.

For every run record model-reported input, cached input, output and reasoning
tokens; elapsed time; tool calls; bytes of every query and read; executed checks;
failed exploration commands; completion/censoring; and each rubric decision.
Report per-pair deltas as well as totals, including failures and the no-hit case.
Separate one-time corpus ingestion/indexing from per-consumer costs and state
the assumed reuse count before amortizing it. Do not claim monetary savings
without verified pricing and actual usage. Retain the raw outputs and artifact
hashes so another assessor can reproduce the decision.

## Executed pilot and protocol deviations (2026-10-05)

`run_consumer_pilot.py OUTPUT_ROOT SOURCE_ROOT` prepares the fixed cases and
uses Codex CLI 0.153.4 with requested `gpt-6-astra`, effort `low`. The backend
model revision was unavailable. `consumer_reference.py` exposes the pinned
MaterialStore query/read API with capture and publication absent; this is not
an installed native MindIE MCP acceptance run. The source revision was
`f5d9b4374ebe8323c465da0b916d8408ee5f0f2f`.

All 12 consumers completed their visible tasks and none queried the optional
reference. Consequently these runs measure uptake, not a treatment effect of
reuse. Two FP16 artifacts failed the private oracle while matching every given
golden: the visible examples did not constrain the hidden intermediate rounding
expectation. Report that specification gap instead of labeling visible tasks
failed. The anonymous review was conducted before the arm key was disclosed.

Usage became available only at two-run wave completion. The initial 240,000
input ceiling was exceeded at four completed runs (276,059). Before resuming,
the ceiling was explicitly amended to 1,200,000; all four results were retained
and the remaining eight ran once (`MINDIE_PILOT_INPUT_BUDGET=1200000`,
`--resume`). The total was 768,588 input including 699,392 cached, 6,427 output
and 239 reasoning-output tokens. Output and tool limits in the prompt are
instructions, not hard host enforcement; record any excess, never hide it.

Two later fresh FP16 contexts received the same additional query/full-read
instruction. This exploratory positive control is separate from the original
pilot and is not a product requirement. The populated reference arm met the
extra hidden rounding rule while the empty-corpus arm did not; both met the
visible goldens. These two used 138,879 input including 119,168 cached and 1,786
output tokens, within a separately recorded 300,000-input budget. Retain the
actual prompt hashes after the additional instruction, not only the base prompt
hashes. No monetary or population-wide quality claim follows from these data.

Sanitized per-run usage, artifact hashes, reference bytes and limitations are in
`../../docs/evidence/reuse-2026-10-05/consumer-results.json`; the paired anonymous
review is adjacent. Raw model events remain local and are not publication data.
