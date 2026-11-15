#!/usr/bin/env python3
"""Automated Pre-PR Checklist and review evidence gate for GitHub Pull Requests.

[Role]
Verifies that a Pull Request description completes all required Pre-PR Checklist
items (`1–8`, `9`, `10–11`, `12–13`, `14`, `15`) and provides substantive Summary,
Review Evidence (`自查结论与证据`), and Verification sections before merge.

[Invariants]
- Pure stdlib validator; zero external dependencies or network calls.
- Rejects any unchecked `- [ ]` items, missing required sections, or placeholder
  one-word/empty bullets (`TODO`, `TBD`, `N/A`, `-`).

[Timeouts & Locks]
- Pure in-memory string parsing (`< 50ms`); acquires no locks.

[Side-Effect Policy]
- Read-only inspection of `GITHUB_EVENT_PATH`, `PR_BODY`, or `--body-file`.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

REQUIRED_CHECKBOX_PREFIXES = (
    "1–8.",
    "9.",
    "10–11.",
    "12–13.",
    "14.",
    "15.",
)

PLACEHOLDERS = frozenset({"todo", "tbd", "n/a", "na", "none", "null", "无", "略", "待补充"})
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
UNCHECKED_RE = re.compile(r"^\s*-\s*\[\s\]\s+(.+)$", re.MULTILINE)
CHECKED_RE = re.compile(r"^\s*-\s*\[[xX]\]\s+\*\*(.+?)\*\*", re.MULTILINE)
EVIDENCE_RE = re.compile(
    r"^\s*-\s*\*\*自查结论与证据\*\*\s*[：:]\s*(.*)$",
    re.MULTILINE,
)


def _strip_comments(text: str) -> str:
    return COMMENT_RE.sub("", text or "")


def _sections(body: str) -> dict[str, str]:
    matches = list(HEADING_RE.finditer(body))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        result[title] = body[start:end].strip()
    return result


def _find_section(sections: dict[str, str], keyword: str) -> str | None:
    for title, content in sections.items():
        if keyword in title:
            return content
    return None


def _substantive_lines(section: str) -> list[str]:
    lines = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line or line.startswith(">"):
            continue
        line = re.sub(r"^[-*+]\s+", "", line).strip()
        if not line or line.lower() in PLACEHOLDERS:
            continue
        lines.append(line)
    return lines


def validate_pr_body(raw_body: str) -> list[str]:
    errors: list[str] = []
    body = _strip_comments(raw_body)
    if not body.strip():
        return ["PR description is empty; please fill out .github/pull_request_template.md."]

    sections = _sections(body)

    summary = _find_section(sections, "变更摘要") or _find_section(sections, "Summary")
    if summary is None:
        errors.append("Missing required section: '## 变更摘要 (Summary)'.")
    else:
        lines = _substantive_lines(summary)
        if not lines or sum(len(line) for line in lines) < 10:
            errors.append("'## 变更摘要 (Summary)' must contain a substantive description (>= 10 chars).")

    review = _find_section(sections, "设计原则 Review") or _find_section(sections, "Pre-PR Checklist")
    if review is None:
        errors.append("Missing required section: '## 设计原则 Review (Pre-PR Checklist)'.")
    else:
        unchecked = UNCHECKED_RE.findall(review)
        if unchecked:
            errors.append(
                f"Found {len(unchecked)} unchecked checklist item(s) ('- [ ]'); "
                "all Pre-PR Checklist items must be reviewed and checked ('- [x]')."
            )
        checked_titles = CHECKED_RE.findall(review)
        for prefix in REQUIRED_CHECKBOX_PREFIXES:
            if not any(title.strip().startswith(prefix) for title in checked_titles):
                errors.append(f"Missing checked Pre-PR Checklist item starting with '{prefix}' ('- [x] **{prefix}...').")

        evidence_match = EVIDENCE_RE.search(review)
        if evidence_match is None:
            errors.append(
                "Missing '- **自查结论与证据**：<具体自查结论>' under '## 设计原则 Review (Pre-PR Checklist)'."
            )
        else:
            inline = evidence_match.group(1).strip()
            trailing = review[evidence_match.end():].strip()
            trailing_lines = _substantive_lines(trailing) if trailing else []
            combined = " ".join(([inline] if inline and inline.lower() not in PLACEHOLDERS else []) + trailing_lines).strip()
            if len(combined) < 15:
                errors.append(
                    "'- **自查结论与证据**：' must include concrete review notes (>= 15 chars, not placeholder/empty)."
                )

    verification = _find_section(sections, "验证结果") or _find_section(sections, "Verification")
    if verification is None:
        errors.append("Missing required section: '## 验证结果 (Verification)'.")
    else:
        lines = _substantive_lines(verification)
        if not lines or sum(len(line) for line in lines) < 10:
            errors.append(
                "'## 验证结果 (Verification)' must record actual executed test commands and results (>= 10 chars)."
            )

    return errors


def _load_body(args: argparse.Namespace) -> str:
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    if "PR_BODY" in os.environ:
        return os.environ["PR_BODY"]
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path and Path(event_path).is_file():
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        pr = payload.get("pull_request") or {}
        return pr.get("body") or ""
    raise SystemExit("No PR body source provided (use --body-file, PR_BODY, or GITHUB_EVENT_PATH).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body-file", help="Path to a markdown file containing the PR body.")
    args = parser.parse_args(argv)
    body = _load_body(args)
    errors = validate_pr_body(body)
    if errors:
        print("Pre-PR Checklist validation failed:", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print("Pre-PR Checklist validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
