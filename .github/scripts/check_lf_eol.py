#!/usr/bin/env python3
"""Automated repository LF line-ending gate rejecting Windows CRLF (\\r\\n).

[Role]
Verifies that repository config (`.gitattributes`, `.editorconfig`) enforces Unix
LF (`\\n`) line endings and that all non-binary tracked/untracked workspace files
contain zero Windows CRLF (`\\r\\n`) or mixed line endings.

[Invariants]
- Pure stdlib validator; streams file chunks (`64 KiB`) with $O(1)$ memory.
- Honors explicit `attr/-text` binary/raw-byte fixture declarations in `.gitattributes`.
- Never silently ignores subprocess or I/O failures.

[Timeouts & Locks]
- Subprocess `git ls-files` bounded by `GIT_TIMEOUT_SECONDS = 15.0`; acquires no locks.

[Side-Effect Policy]
- Read-only inspection of `.gitattributes`, `.editorconfig`, and Git workspace files.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

GIT_TIMEOUT_SECONDS = 15.0
STREAM_CHUNK_BYTES = 65536


def _has_carriage_return(path: Path) -> bool:
    with path.open("rb") as handle:
        while chunk := handle.read(STREAM_CHUNK_BYTES):
            if b"\r" in chunk:
                return True
    return False


def validate_repo_lf(repo_root: Path) -> list[str]:
    errors: list[str] = []
    gitattributes = repo_root / ".gitattributes"
    if not gitattributes.is_file():
        errors.append("Missing '.gitattributes' at repository root (must declare '* text=auto eol=lf').")
    else:
        attr_text = gitattributes.read_text(encoding="utf-8", errors="replace")
        if "* text=auto eol=lf" not in attr_text:
            errors.append("'.gitattributes' must contain '* text=auto eol=lf' to prohibit Windows CRLF.")

    editorconfig = repo_root / ".editorconfig"
    if not editorconfig.is_file():
        errors.append("Missing '.editorconfig' at repository root (must declare 'end_of_line = lf').")
    else:
        ec_text = editorconfig.read_text(encoding="utf-8", errors="replace")
        if "end_of_line = lf" not in ec_text:
            errors.append("'.editorconfig' must contain 'end_of_line = lf'.")

    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--cached", "--others", "--exclude-standard", "--eol", "-z"],
        capture_output=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        return errors + [f"git ls-files --eol failed (exit {proc.returncode}): {stderr}"]

    for raw_entry in proc.stdout.split(b"\x00"):
        if not raw_entry:
            continue
        entry = raw_entry.decode("utf-8", errors="surrogateescape")
        if "\t" not in entry:
            continue
        meta, rel_path = entry.split("\t", 1)
        tokens = meta.split()
        i_eol = tokens[0] if len(tokens) > 0 else ""
        w_eol = tokens[1] if len(tokens) > 1 else ""
        attr_info = " ".join(tokens[2:])

        # Skip Git-detected binary files or files explicitly marked -text in .gitattributes
        attr_tokens = set(attr_info.split())
        if i_eol == "i/-text" or w_eol == "w/-text" or "attr/-text" in attr_tokens or "-text" in attr_tokens:
            continue

        if i_eol in ("i/crlf", "i/mixed") or w_eol in ("w/crlf", "w/mixed"):
            errors.append(
                f"{rel_path}: forbidden Windows CRLF / mixed line endings ({i_eol} {w_eol}); "
                "must use Unix LF (\\n)."
            )
            continue

        file_path = repo_root / rel_path
        if file_path.is_file() and not file_path.is_symlink():
            if _has_carriage_return(file_path):
                errors.append(
                    f"{rel_path}: contains raw '\\r' (CRLF/CR) bytes on disk; must use Unix LF (\\n)."
                )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Path to the repository root to inspect.",
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    errors = validate_repo_lf(repo_root)
    if errors:
        print("LF line-ending validation failed (Windows CRLF is prohibited):", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        print(
            "Hint: convert offending files to LF (e.g., `git add --renormalize .` or strip `\\r`).",
            file=sys.stderr,
        )
        return 1
    print(f"LF line-ending validation passed ({repo_root.name}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
