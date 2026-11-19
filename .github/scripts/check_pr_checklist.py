#!/usr/bin/env python3
"""Parameterized Pre-PR Checklist validator across all 8 MindIE Agent repository classes.

[Role]
Verifies that a Pull Request description completes required machine-stable checklist IDs for
`--profile {hub,harness,host-plugin,control-plane,state-service,device-tool,bench,corpus}`,
with substantive Summary, Evidence (`not-applicable: <specific reason>`), and Verification.

[Invariants]
- Pure stdlib; strips HTML comments and CommonMark code fences before parsing checkboxes.
- Rejects unreplaced `<template>` and TODO/TBD markers, empty or self-echoed per-command
  Verification results, and per-ID evidence that merely echoes the checkbox prompt.

[Timeouts & Locks]
- Pure in-memory string parsing (`< 20ms`); acquires no locks.

[Side-Effect Policy]
- Read-only inspection of `--body-file`, `PR_BODY`, or `GITHUB_EVENT_PATH`.
"""
from __future__ import annotations
import argparse, json, os, re, sys
from pathlib import Path

PROFILE_ITEMS: dict[str, tuple[str, ...]] = {
    "hub": ("HUB-ROUTE", "HUB-DOC", "HUB-RELEASE", "HUB-GATE"), "harness": ("HAR-ABI", "HAR-UPGRADE", "HAR-PROC", "HAR-STATE"),
    "host-plugin": ("HOST-NATIVE", "HOST-WIRE", "HOST-ADMISSION", "HOST-UPGRADE"), "control-plane": ("CTRL-LEASE-OR-AUTH", "CTRL-HANDLE", "CTRL-STREAM-IO", "CTRL-RECEIPT"),
    "state-service": ("SVC-CONSENT", "SVC-STATE-COMPAT", "SVC-LIFETIME", "SVC-EXPORT"), "device-tool": ("DEV-ZERO-CTX", "DEV-READONLY-PATH", "DEV-TOPOLOGY", "DEV-BOUNDED-MEM"),
    "bench": ("BENCH-ORACLE", "BENCH-VERDICT", "BENCH-PROVENANCE", "BENCH-ISOLATION"), "corpus": ("CORPUS-SCHEMA", "CORPUS-EVIDENCE", "CORPUS-REDACT", "CORPUS-REVISION"),
}
PLACEHOLDERS = frozenset({"todo", "tbd", "n/a", "na", "none", "null", "-", "无", "略", "待补充", "待填写"})
HTML_TAGS = frozenset({"a", "b", "br", "code", "details", "div", "em", "i", "img", "li", "ol", "p", "pre", "span", "strong", "sub", "summary", "sup", "table", "td", "th", "tr", "ul"})
STOCK_COLON_PREFIXES = ("sharedremotedevsshauth", "hostqueuephysicalnpuport", "standardzerometamcptools", "allstandaloneremoteworker", "remotestandaloneworkerscripts", "externalmutationsdistinguish")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")
HEADING_RE = re.compile(r"^[ \t]{0,3}##\s+(.+?)\s*$", re.MULTILINE)
CHECKBOX_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(?:\*\*|`)*([A-Z]+(?:-[A-Z0-9]+)+(?![A-Z0-9_-]))?(?:\*\*|`)*(.*)$", re.MULTILINE)
INLINE_EVIDENCE_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s*(?:\*\*|`)*([A-Z]+(?:-[A-Z0-9]+)+)(?![A-Z0-9_-])(?:\*\*|`)*[ \t]*[：:][ \t]*([^\n]+)$")
ID_EVIDENCE_RE = re.compile(r"^\s*(?:[-*+]\s*)?(?:\*\*|`)*([A-Z]+(?:-[A-Z0-9]+)+)(?![A-Z0-9_-])(?:\*\*|`)*[ \t]*[：:—-][ \t]*([^\n]*)$")
SUMMARY_EVIDENCE_RE = re.compile(r"^[ \t]*-[ \t]*\*\*(?:自查结论与证据|Review Evidence)\*\*[ \t]*[：:][ \t]*([^\n]*)$", re.MULTILINE)
VERIF_BACKTICK_RE = re.compile(r"^\s*[-*+]\s*`([^`\n]+)`[ \t]*(?:[：:—-][ \t]*)?([^\n]*)$")
VERIF_COLON_RE = re.compile(r"^\s*[-*+]\s*([^`\n]+?)[：:](?=[ \t]|$)[ \t]*([^\n]*)$")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
NA_HINT_CODE_RE = re.compile(r"`not-applicable:\s*<[^`\n]*>`", re.IGNORECASE)
TEMPLATE_RE = re.compile(r"<(?![<>=]?\s*[\d.])([^<>\s][^<>\n]*)>")
TODO_RE = re.compile(r"\b(?:TODO|TBD)\b|待补充|待填写", re.IGNORECASE)
ECHO_PREFIX_RE = re.compile(r"^(?:(?:verified|checked|confirmed|validated|reviewed|已核验|已验证|已确认)\s*[:：—-]?\s*)+")

def _strip_fences(text: str) -> str:
    out, f_char, f_len = [], "", 0
    for line in text.splitlines():
        if f_char:
            s = line.lstrip(" \t")
            if len(line) - len(s) <= 3 and s.rstrip(" \t") and set(s.rstrip(" \t")) == {f_char} and len(s.rstrip(" \t")) >= f_len:
                f_char, f_len = "", 0
        elif (m := FENCE_OPEN_RE.match(line)) and (m.group(1)[0] == "~" or "`" not in m.group(2)):
            f_char, f_len = m.group(1)[0], len(m.group(1))
        else:
            out.append(line)
    return "\n".join(out)

def _sections(body: str) -> dict[str, str]:
    ms = list(HEADING_RE.finditer(body))
    return {m.group(1).strip(): body[m.end() : (ms[i + 1].start() if i + 1 < len(ms) else len(body))].strip() for i, m in enumerate(ms)}

def _find(secs: dict[str, str], *kws: str) -> str | None:
    return next((v for k, v in secs.items() if any(w.lower() in k.lower() for w in kws)), None)

def _unwrapped(text: str) -> str:
    return re.sub(r"^[-*+]\s+", "", text.strip()).strip().strip("`*_").strip()

def _is_placeholder_angle(token: str) -> bool:
    parts = token.strip().strip("/").split()
    return (parts[0].lower() if parts else "") not in HTML_TAGS and not token.strip().lower().startswith(("http://", "https://", "mailto:"))

def _is_valid_note(note: str) -> bool:
    clean = _unwrapped(note)
    if not clean or clean.lower() in PLACEHOLDERS or any(_is_placeholder_angle(t.group(1)) for t in TEMPLATE_RE.finditer(note)):
        return False
    if clean.lower().startswith("not-applicable"):
        _, sep, reason = clean.partition(":")
        return bool(sep) and len(r := _unwrapped(reason)) >= 6 and r.lower() not in PLACEHOLDERS
    return len(clean) >= 8

def _substantive_text(sec: str) -> str:
    lns = [_unwrapped(ln) for ln in sec.splitlines() if ln.strip() and not ln.lstrip().startswith(">")]
    return " ".join(ln for ln in lns if ln and ln.lower() not in PLACEHOLDERS)

def _normalized_echo(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", ECHO_PREFIX_RE.sub("", _unwrapped(value).lower()))

def _placeholder_errors(body: str) -> list[str]:
    non_quote = [ln for ln in body.splitlines() if not ln.lstrip().startswith(">")]
    scan = "\n".join(NA_HINT_CODE_RE.sub("", ln) if CHECKBOX_RE.match(ln) else ln for ln in non_quote)
    errors = [f"Unreplaced template placeholder {m.group(0)!r}; fill in concrete content."
              for m in TEMPLATE_RE.finditer(scan) if _is_placeholder_angle(m.group(1))]
    errors.extend(f"Unresolved '{m.group(0)}' marker outside inline code."
                  for m in TODO_RE.finditer(INLINE_CODE_RE.sub("", "\n".join(non_quote))))
    return errors

def _verification_errors(verif: str) -> list[str]:
    errors: list[str] = []
    for line in verif.splitlines():
        if line.lstrip().startswith(">") or not (m := VERIF_BACKTICK_RE.match(line) or VERIF_COLON_RE.match(line)):
            continue
        cmd, res = m.group(1).strip(), m.group(2).strip()
        clean_res = _unwrapped(res)
        bad_na = clean_res.lower().startswith("not-applicable") and not _is_valid_note(res)
        has_tpl = any(_is_placeholder_angle(t.group(1)) for t in TEMPLATE_RE.finditer(res))
        if (not clean_res or clean_res.lower() in PLACEHOLDERS or bad_na or has_tpl
                or TODO_RE.search(INLINE_CODE_RE.sub("", res)) or _normalized_echo(clean_res) == _normalized_echo(cmd)):
            errors.append(f"Verification command `{cmd}` needs a concrete non-placeholder result.")
    return errors

def _evidence_errors(ev_text: str, profile: str) -> list[str]:
    targets, titles, inline, separate = set(PROFILE_ITEMS[profile]), {}, {}, {}
    for line in ev_text.splitlines():
        if box := CHECKBOX_RE.match(line):
            _, item_id, rest = box.groups()
            if item_id:
                titles.setdefault(item_id, re.sub(r"^[\s：:—-]+", "", rest))
                if (m_in := INLINE_EVIDENCE_RE.match(line)) and "`not-applicable: <" not in line.lower():
                    if not _normalized_echo(val := m_in.group(2).strip()).startswith(STOCK_COLON_PREFIXES):
                        inline.setdefault(item_id, val)
        elif not line.lstrip().startswith(">") and (ev := ID_EVIDENCE_RE.match(line)) and ev.group(1) in targets:
            separate.setdefault(ev.group(1), []).append(ev.group(2).strip())
    if separate or inline:
        errors: list[str] = []
        for item_id in PROFILE_ITEMS[profile]:
            rows = separate[item_id] if item_id in separate else ([inline[item_id]] if item_id in inline else [])
            title_norm = _normalized_echo(titles.get(item_id, ""))
            if item_id in separate and title_norm and any(_normalized_echo(r) == title_norm for r in rows):
                errors.append(f"Checklist ID '{item_id}' evidence only echoes the checkbox prompt; provide concrete verification.")
            elif not rows or not _is_valid_note(" ".join(rows)):
                errors.append(f"Checklist ID '{item_id}' requires concrete evidence or 'not-applicable: <specific reason>'.")
        return errors
    if m := SUMMARY_EVIDENCE_RE.search(ev_text):
        tail = []
        for ln in ev_text[m.end() :].splitlines():
            if CHECKBOX_RE.match(ln) or ID_EVIDENCE_RE.match(ln): break
            tail.append(ln)
        if _is_valid_note(note := (m.group(1).strip() + " " + _substantive_text("\n".join(tail))).strip()) and len(note) >= 15: return []
    return ["Provide per-ID evidence ('ID: <evidence | not-applicable: reason>') or '- **自查结论与证据**: <notes>'."]

def validate_pr_body(raw_body: str, *, profile: str = "hub") -> list[str]:
    if profile not in PROFILE_ITEMS:
        raise ValueError(f"Unsupported profile {profile!r}; expected one of {tuple(PROFILE_ITEMS)}")
    body = _strip_fences(COMMENT_RE.sub("", (raw_body or "").replace("\r\n", "\n").replace("\r", "\n")))
    if not body.strip():
        return ["PR description is empty; fill out .github/pull_request_template.md."]
    secs, errors = _sections(body), _placeholder_errors(body)
    if (summary := _find(secs, "Summary", "变更摘要")) is None or len(_substantive_text(summary)) < 10:
        errors.append("Missing or placeholder '## 变更摘要 (Summary)' (>= 10 substantive chars required).")
    if (review := _find(secs, "Pre-PR Checklist", "设计原则 Review", "Review")) is None:
        errors.append("Missing required checklist section ('## 设计原则 Review (Pre-PR Checklist)' or '## Review').")
    else:
        checked_ids: list[str] = []
        for mark, item_id, rest in CHECKBOX_RE.findall(review):
            if mark == " ":
                errors.append(f"Unchecked checklist item: '{((item_id or '') + ' ' + rest).strip()}'.")
            elif item_id:
                if item_id in checked_ids:
                    errors.append(f"Duplicate checklist ID: '{item_id}'.")
                checked_ids.append(item_id)
        errors.extend(f"Missing checked checklist ID '{cid}' for profile '{profile}'." for cid in PROFILE_ITEMS[profile] if cid not in checked_ids)
        errors.extend(_evidence_errors("\n".join(filter(None, [review, _find(secs, "Evidence", "自查证据")])), profile))
    if (verif := _find(secs, "Verification", "验证结果")) is None or not _is_valid_note(_substantive_text(verif)):
        errors.append("Missing or placeholder '## 验证结果 (Verification)'.")
    else:
        errors.extend(_verification_errors(verif))
    return errors

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(PROFILE_ITEMS), default="hub")
    parser.add_argument("--body-file", help="Path to markdown file containing PR body.")
    args = parser.parse_args(argv)
    raw = (Path(args.body_file).read_text(encoding="utf-8") if args.body_file else os.environ["PR_BODY"] if "PR_BODY" in os.environ
           else (json.loads(Path(ep).read_text(encoding="utf-8")).get("pull_request") or {}).get("body") or ""
           if (ep := os.environ.get("GITHUB_EVENT_PATH")) and Path(ep).is_file() else None)
    if raw is None:
        raise SystemExit("No PR body source provided (use --body-file, PR_BODY, or GITHUB_EVENT_PATH).")
    if errors := validate_pr_body(raw, profile=args.profile):
        print("\n".join([f"Pre-PR Checklist validation failed (profile={args.profile}):", *(f"  - {e}" for e in errors)]), file=sys.stderr)
        return 1
    print(f"Pre-PR Checklist validation passed (profile={args.profile}).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
