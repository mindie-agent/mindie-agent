# Release benchmark results

Release gate: **pass**

Functional checks, microbenchmarks and E2E measurements have separate scope. Command wall time includes process startup. No causal productivity or NPU performance claim follows from functional checks or CPU microbenchmarks.

Repository: `mindie-agent/knowledge`; version: `0.13.2`
Revision: `b616a38f77ca17573e4ed22ee23c08c09adefac7`; dirty: `False`
Runner revision: `3bf7fa6efc111876cc31c602f11dcd0c029769d7`
Suite: `core`; environment: `linux/x86_64`

| Case | Kind | Status | Repetitions | Metric | Median | Unit |
| --- | --- | --- | --- | --- | --- | --- |
| graded-feed-lifecycle | functional | pass | 1/1 | graded_feed_lifecycle | 368.766 | ms/run |
| technical-tokenization | microbenchmark | pass | 5/5 | technical_tokenization | 69.2043 | us/op |
