#!/usr/bin/env python3
"""Parameterized Pre-PR Checklist validator across all 8 MindIE Agent repository classes.

[Role]
Verifies that a Pull Request description completes the required machine-stable checklist IDs
for `--profile {hub,harness,host-plugin,control-plane,state-service,device-tool,bench,corpus}`,
paired with substantive Summary, Evidence (supporting `not-applicable: <specific reason>`),
and Verification sections.

[Invariants]
- Pure Python stdlib; zero external dependencies, subprocesses, or network calls.
- Strips HTML comments and fenced code blocks (` ``` ` / `~~~`) before parsing checkboxes.

[Timeouts & Locks]
- Pure in-memory string parsing (`< 20ms`); acquires no locks.

[Side-Effect Policy]
- Read-only inspection of `--body-file`, `PR_BODY`, or `GITHUB_EVENT_PATH`.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

PROFILE_ITEMS: dict[str, tuple[str, ...]] = {
    "hub": ("HUB-ROUTE", "HUB-DOC", "HUB-RELEASE", "HUB-GATE"),
    "harness": ("HAR-ABI", "HAR-UPGRADE", "HAR-PROC", "HAR-STATE"),
    "host-plugin": ("HOST-NATIVE", "HOST-WIRE", "HOST-ADMISSION", "HOST-UPGRADE"),
    "control-plane": ("CTRL-LEASE-OR-AUTH", "CTRL-HANDLE", "CTRL-STREAM-IO", "CTRL-RECEIPT"),
    "state-service": ("SVC-CONSENT", "SVC-STATE-COMPAT", "SVC-LIFETIME", "SVC-EXPORT"),
    "device-tool": ("DEV-ZERO-CTX", "DEV-READONLY-PATH", "DEV-TOPOLOGY", "DEV-BOUNDED-MEM"),
    "bench": ("BENCH-ORACLE", "BENCH-VERDICT", "BENCH-PROVENANCE", "BENCH-ISOLATION"),
    "corpus": ("CORPUS-SCHEMA", "CORPUS-EVIDENCE", "CORPUS-REDACT", "CORPUS-REVISION"),
}
PLACEHOLDERS = frozenset({"todo", "tbd", "n/a", "na", "none", "null", "-", "无", "略", "待补充"})
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
FENCE_RE = re.compile(r"^(?:```|~~~).*?^(?:```|~~~)\s*$", re.MULTILINE | re.DOTALL)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
CHECKBOX_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(?:\*\*|`)*([A-Z]+(?:-[A-Z0-9]+)+)?(?:\*\*|`)*(.*)$", re.MULTILINE)
ID_EVIDENCE_RE = re.compile(r"^\s*(?:[-*+]\s*(?:\[[ xX]\]\s*)?)?(?:\*\*|`)*([A-Z]+(?:-[A-Z0-9]+)+)(?:\*\*|`)*\s*[：:—-]\s*(.+)$", re.MULTILINE)
SUMMARY_EVIDENCE_RE = re.compile(r"^\s*-\s*\*\*(?:自查结论与证据|Review Evidence)\*\*\s*[：:]\s*(.*)$", re.MULTILINE)


def _sections(body: str) -> dict[str, str]:
    ms = list(HEADING_RE.finditer(body))
    return {m.group(1).strip(): body[m.end() : (ms[i + 1].start() if i + 1 < len(ms) else len(body))].strip() for i, m in enumerate(ms)}


def _find(secs: dict[str, str], *kws: str) -> str | None:
    return next((v for k, v in secs.items() if any(w.lower() in k.lower() for w in kws)), None)


def _is_valid_note(note: str) -> bool:
    clean = re.sub(r"^[-*+]\s+", "", note.strip()).strip()
    if not clean or clean.lower() in PLACEHOLDERS:
        return False
    if clean.lower().startswith("not-applicable"):
        _, sep, reason = clean.partition(":")
        return bool(sep) and len(r := reason.strip()) >= 6 and r.lower() not in PLACEHOLDERS
    return len(clean) >= 8


def _substantive_text(sec: str) -> str:
    lns = [re.sub(r"^[-*+]\s+", "", ln.strip()).strip() for ln in sec.splitlines() if ln.strip() and not ln.strip().startswith(">")]
    return " ".join(ln for ln in lns if ln and ln.lower() not in PLACEHOLDERS)


def validate_pr_body(raw_body: str, *, profile: str = "hub") -> list[str]:
    if profile not in PROFILE_ITEMS:
        raise ValueError(f"Unsupported profile {profile!r}; expected one of {tuple(PROFILE_ITEMS)}")
    body = FENCE_RE.sub("", COMMENT_RE.sub("", raw_body or ""))
    if not body.strip():
        return ["PR description is empty; fill out .github/pull_request_template.md."]
    secs, errors = _sections(body), []
    if (summary := _find(secs, "Summary", "变更摘要")) is None or len(_substantive_text(summary)) < 10:
        errors.append("Missing or placeholder '## 变更摘要 (Summary)' (>= 10 substantive chars required).")
    if (review := _find(secs, "Pre-PR Checklist", "设计原则 Review", "Review")) is None:
        errors.append("Missing required checklist section ('## 设计原则 Review (Pre-PR Checklist)' or '## Review').")
    else:
        checked_ids: list[str] = []
        for mark, item_id, rest in CHECKBOX_RE.findall(review):
            if mark == " ":
                errors.append(f"Unchecked checklist item: '{(item_id + ' ' + rest).strip()}'.")
            elif item_id:
                if item_id in checked_ids:
                    errors.append(f"Duplicate checklist ID: '{item_id}'.")
                checked_ids.append(item_id)
        for req_id in PROFILE_ITEMS[profile]:
            if req_id not in checked_ids:
                errors.append(f"Missing checked checklist ID '{req_id}' for profile '{profile}'.")
        ev_text = "\n".join(filter(None, [review, _find(secs, "Evidence", "自查证据")]))
        per_id = {cid: val.strip() for cid, val in ID_EVIDENCE_RE.findall(ev_text) if cid in PROFILE_ITEMS[profile]}
        if per_id:
            for req_id in PROFILE_ITEMS[profile]:
                if req_id not in per_id or not _is_valid_note(per_id[req_id]):
                    errors.append(f"Checklist ID '{req_id}' requires concrete evidence or 'not-applicable: <specific reason>'.")
        else:
            m = SUMMARY_EVIDENCE_RE.search(ev_text)
            note = (m.group(1).strip() + " " + _substantive_text(ev_text[m.end() :])).strip() if m else ""
            if not _is_valid_note(note) or len(note) < 15:
                errors.append("Provide per-ID evidence ('ID: <evidence | not-applicable: reason>') or '- **自查结论与证据**: <notes>'.")
    if (verif := _find(secs, "Verification", "验证结果")) is None or not _is_valid_note(_substantive_text(verif)):
        errors.append("Missing or placeholder '## 验证结果 (Verification)'.")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(PROFILE_ITEMS), default="hub")
    parser.add_argument("--body-file", help="Path to markdown file containing PR body.")
    args = parser.parse_args(argv)
    if args.body_file:
        raw = Path(args.body_file).read_text(encoding="utf-8")
    elif "PR_BODY" in os.environ:
        raw = os.environ["PR_BODY"]
    elif (ep := os.environ.get("GITHUB_EVENT_PATH")) and Path(ep).is_file():
        raw = (json.loads(Path(ep).read_text(encoding="utf-8")).get("pull_request") or {}).get("body") or ""
    else:
        raise SystemExit("No PR body source provided (use --body-file, PR_BODY, or GITHUB_EVENT_PATH).")
    if errors := validate_pr_body(raw, profile=args.profile):
        print(f"Pre-PR Checklist validation failed (profile={args.profile}):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"Pre-PR Checklist validation passed (profile={args.profile}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
