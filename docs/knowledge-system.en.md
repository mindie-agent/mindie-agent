# Knowledge & Experience System Design

[中文](knowledge-system.md) · [Back to Documentation Center](README.en.md)

This document explains how MindIE Agent turns real-world Ascend NPU debugging and engineering sessions into structured, reusable Markdown knowledge packages—while keeping private data safe and context windows lean.

- Governed by: [Engineering Design Principles](design-principles.en.md) · [Architecture & Module Boundaries](architecture.en.md)
- Core Engine Repository: [`mindie-agent/knowledge`](https://github.com/mindie-agent/knowledge)
- Public Domain Corpus: [`mindie-agent/knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend)

---

## 1. Five Core Design Ideas

1. **Preserve the Complete Primary Conversation—Never Replace It with a Summary**
   - Many memory systems ask an LLM to rewrite a debugging session into a short paragraph, losing the exact stack traces, environment variables, and diagnostic turning points that actually matter.
   - In MindIE Agent, extracting and redacting public conversation turns is done entirely by **deterministic code** and saved as immutable, ordered Markdown blocks (`materials/0001.md`, `0002.md`, ...). No LLM ever rewrites the body text or truncates the middle of a long task.
2. **Use a Lightweight Native Model Only to Build the "Table of Contents"**
   - So Agents don't have to load massive transcripts into context, each Harness plugin uses its lightweight native model (with LangMem) strictly to generate block titles, search summaries, and a task-level navigation manifest (`PACKAGE.md`).
   - When searching, the Agent reads `PACKAGE.md` first to see the big picture, then loads only the specific block(s) it needs (e.g., `#0002`).
3. **Two-Layer Storage Isolation with One Unified Format**
   - Curated community knowledge (`public/`) and private local task records (`local/`) live in separate directories on disk but share the exact same `mindie-material-task/1` package format and rebuildable ReMe search index.
4. **Fail-Closed Privacy & Explicit Consent**
   - Nothing is collected without explicit project-scope consent. Before any bytes are written to disk, sent to the indexing model, or proposed in a public PR, deterministic privacy rules and Gitleaks secret scanning run automatically.
5. **Advisory Knowledge with Real-World Usefulness Feedback**
   - Knowledge entries are helpful reference leads, never mandatory rules. After consulting an entry in a real task, the consuming Agent can submit `helpful` or `not_helpful` feedback to help the corpus evolve.

---

## 2. End-to-End Pipeline: From Session to Knowledge Package

```mermaid
flowchart TB
    T["Verified Host Session Transcript"] --> P["1. Deterministic Public Message Extraction<br/>(Keep only user input, public progress & final answer)"]
    P --> R["2. Deterministic Privacy Rules + Gitleaks Redaction"]
    R --> B["3. Write Immutable Markdown Blocks<br/>(materials/0001.md, 0002.md...)"]
    B --> I["4. Lightweight Native Model Builds Navigation<br/>(Update PACKAGE.md & advance SQLite cursor)"]
    I --> L["5. Update Local Rebuildable ReMe Index<br/>(BM25 + Hybrid Search)"]
    I --> O{"Community Sharing Enabled?"}
    O -->|No (Local Reuse Only)| L
    O -->|Yes| G["6. Automatically Open Public Package PR<br/>(knowledge-vllm-ascend)"]
    G --> Bot["7. Grok Bot Safety & Compliance Review"]
    Bot --> Sync["8. Incremental Client Sync (public/)"]
```

### 2.1 Step 1: Deterministic Public Message Extraction
- The plugin reads only the explicitly verified transcript of the current task—never scanning arbitrary historical sessions.
- **Only three message types are kept**: **User Input**, **Public Assistant Progress**, and **Final Answers**.
- **Internal noise is stripped**: Raw tool call payloads, hidden reasoning chains, system-injected instructions, and duplicate host wrapper events are deterministically removed.

### 2.2 Step 2: Multi-Stage Privacy Redaction & Safety Gate
- Before writing to disk, calling the indexing model, or opening a PR, `mindie_knowledge.redact` and Gitleaks scanning run automatically.
- Secrets, tokens, private keys, private IPv4 ranges, SSH `user@host` endpoints, local home directory paths (`/Users/...`, `/home/...`, `C:\Users\...`), and email addresses are redacted or blocked.
- **Defense in depth**: Pattern redaction complements explicit consent—only tasks inside the user's authorized project scope are admitted.

### 2.3 Step 3: Immutable Blocks & Small-Model Navigation
- Redacted turns are split sequentially into immutable `mindie-material-block/1` files (`materials/0001.md`, `0002.md`, ...).
- The adapter's lightweight model generates titles, retrieval summaries, and applicability `conditions` for new blocks, updating `PACKAGE.md`.
- Long tasks advance incrementally via durable cursors. If an indexing model call fails, the saved Markdown blocks remain intact on disk and the unfinished stage is reported honestly without faking completion or blindly retrying uncertain paid calls.

---

## 3. What a Knowledge Package Looks Like (`tasks/<task_hash>/`)

Both local experience packages and public packages in [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend) follow the exact same directory layout:

```text
tasks/<task_hash>/
├── PACKAGE.md           # Task manifest (mindie-material-task/1 + mindie-entry/3 header, summary & block table)
└── materials/
    ├── 0001.md          # Ordered redacted conversation block 1 (mindie-material-block/1)
    ├── 0002.md          # Ordered redacted conversation block 2
    └── ...
```

- **Read the Outline First (`tasks/<task_hash>`)**: Returns `PACKAGE.md` with the overall problem summary, applicability conditions, and block table of contents.
- **Read Specific Blocks on Demand (`tasks/<task_hash>#0001`)**: Returns that exact block's Markdown body, file hash, and adjacent block pointers so the Agent loads only the context it needs.

---

## 4. Authoritative Markdown Storage & Rebuildable Indexes

- **Markdown Is the Source of Truth**:
  - **Markdown files** on disk are the sole authoritative store for conversation content;
  - **SQLite** stores compact cursors, queues, consent bindings, and external operation receipts;
  - **ReMe** maintains an in-process search index that can be rebuilt from the Markdown files at any time. If SQLite is missing or corrupted, the runtime reports a clear error and protects all existing Markdown files rather than treating it as a fresh install.
- **Citations & Feedback**:
  - Literal citations inside blocks participate in search grouping only when the cited package also matches the current query; citation count never implies official certification.
  - Consuming tasks can optionally submit `helpful` or `not_helpful` feedback after real use to improve ranking and guide corpus maintenance.
