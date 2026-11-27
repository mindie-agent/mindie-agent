#!/usr/bin/env python3
"""Lean code and living-document hygiene gate across the MindIE Agent repository family.

[Role]
Verifies clean production Python surfaces (no legacy/shadow filenames, unproven version families,
or unreachable modules) and active bilingual living-document hygiene (links, anchors, inline file
paths, published release indexes, translation pairs, and symmetric `##` sections).

[Invariants]
- Pure Python 3.11+ stdlib (`ast`, `importlib.util`, `json`, `posixpath`, `re`, `subprocess`, `tomllib`).
- `main_repo` is inspected only when supplied; synthetic `main_repo=None` calls never probe the Hub.
  Sibling floors apply unless `required_repos` or `--enforce-all` selects them.
- Real checkouts use `git ls-files --cached`; Tier-0 fixtures walk while pruning build/runtime state.
- `Upstream-ABI:` markers must be distinct, externally imported, and grounded in non-docstring AST symbols.

[Timeouts & Locks]
- Git inventory enforces `15s` (windowless on Windows); single-pass AST keeps peak RSS bounded.

[Side-Effect Policy]
- Strictly read-only inspection of repository checkouts; never rewrites code, docs, or Git state.
"""
from __future__ import annotations
import argparse, ast, importlib.util, json, os, posixpath, re, subprocess, sys, tomllib, urllib.parse
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from repo_roots import (
    ALL_KNOWN_REPOS, HUB_REPO, INDEPENDENT_COMPONENTS, INDEPENDENT_PLUGINS,
    RepoCoverage, infer_default_siblings_roots, parse_repo_overrides, resolve_repo,
)
from storage_lifecycle_gate import PRODUCTION_PYTHON_SCOPES, VERSION_MANIFESTS

CODE_DOC_HYGIENE_FLOOR_VERSIONS: dict[str, tuple[int, int, int]] = {
    "harness": (0, 1, 5), "diagnostics": (0, 5, 18), "debugger": (0, 1, 5),
    "profiler": (0, 5, 17), "sim": (0, 9, 19), "npu-top": (0, 3, 6),
    "remote-dev": (0, 11, 15), "knowledge": (0, 13, 25), "coordinator": (0, 7, 14),
    "mindie-bench": (0, 4, 15), "mindie-agent-codex": (0, 1, 40),
    "mindie-agent-cc": (0, 1, 32), "mindie-agent-kimi": (0, 1, 33),
    "mindie-agent-dsh": (0, 1, 28), "mindie-agent-agy": (0, 1, 22),
    "mindie-agent-wb": (0, 1, 20), "mindie-agent-oc": (0, 1, 12),
    "mindie-agent-omp": (1, 3, 0),
}
_INDEPENDENT_EXEMPT = frozenset({*INDEPENDENT_COMPONENTS, *INDEPENDENT_PLUGINS})
_LEGACY_STEM_RE = re.compile(r"^(.+)_(?:legacy|old|backup|fallback)$")
_COPY_STEM_RE = re.compile(r"^(.+)_copy$")
_VERSION_STEM_RE = re.compile(r"^(?P<base>.+)_v(?P<ver>\d+)$")
_ABI_RE = re.compile(r"Upstream-ABI:[ \t]*(\S+)")
_ABI_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]{3,}$")
_ABI_GENERIC = frozenset({"v1", "v2", "v3", "v4", "legacy", "internal", "custom", "default", "none", "todo", "refactor", "fallback"})
_SKIP_PARTS = frozenset({".git", "__pycache__", "node_modules", "dist", "build", ".venv", "venv", ".pytest_cache",
    "repositories", "data", "state", "reports", "baselines", "third_party"})
_SKIP_TESTS = frozenset({"tests", "test", "benchmarks", "fixtures"})
_MANIFEST_SUFFIXES = frozenset({".json", ".mjs", ".cjs", ".js", ".ts", ".yml", ".yaml", ".sh", ".ps1", ".cmd"})
_MANIFEST_SKIP_DIRS = frozenset({"docs", "data", "state", "reports", "baselines", "tests", "test", "benchmarks", "fixtures"})
_DOC_SKIP_PREFIXES = ("docs/archive/", "docs/releases/", "docs/audits/")
_HISTORICAL_ROOT_DOCS = frozenset({"CHANGELOG.md", "THIRD_PARTY_NOTICES.md"})
_HEADING_CUSTOM_ID_RE = re.compile(r"\{#([A-Za-z0-9_:-]+)\}")
_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")
_SCRIPT_IMPORT_ROOTS = (".github/scripts", "plugins/mindie-agent/scripts", "scripts")
_PATH_CTORS = frozenset({"Path", "PurePath", "PurePosixPath", "PureWindowsPath"})
_INLINE_PATH_SUFFIXES = frozenset({".py", ".pyi", ".md", ".json", ".toml", ".yml", ".yaml", ".mjs", ".cjs",
    ".js", ".ts", ".sh", ".ps1", ".cmd", ".txt", ".cfg", ".ini", ".lock", ".jsonl", ".csv", ".whl"})

def _is_real_git(repo_dir: Path) -> bool:
    return (repo_dir / ".git").is_file() or (repo_dir / ".git" / "HEAD").is_file()

def _version(repo_dir: Path, repo: str) -> tuple[tuple[int, int, int] | None, str | None]:
    parse_err: str | None = None
    for rel in VERSION_MANIFESTS:
        manifest = repo_dir / rel
        if not manifest.is_file():
            continue
        try:
            raw = manifest.read_text(encoding="utf-8")
            meta = tomllib.loads(raw).get("project", {}) if manifest.suffix == ".toml" else json.loads(raw)
        except TimeoutError:
            raise
        except (OSError, ValueError) as exc:
            parse_err = f"{repo}: failed reading version manifest {rel}: {exc}"
            continue
        if not (ver_str := str((meta or {}).get("version") or "").strip()):
            continue
        if match := re.match(r"^(\d+)\.(\d+)\.(\d+)", ver_str):
            return (int(match.group(1)), int(match.group(2)), int(match.group(3))), None
        parse_err = f"{repo}: invalid SemVer {ver_str!r} in {rel}"
    return None, parse_err

def _tracked(repo_dir: Path, repo: str) -> tuple[list[str], list[str]]:
    if not repo_dir.is_dir():
        return [], [f"{repo}: repository directory does not exist: {repo_dir}"]
    if _is_real_git(repo_dir):
        from host_compatibility_gate import subprocess_window_kwargs
        try:
            proc = subprocess.run(
                ["git", "-C", str(repo_dir), "ls-files", "--cached", "-z"],
                capture_output=True, timeout=15.0, check=False,
                **subprocess_window_kwargs(os_mod=os, subprocess_mod=subprocess),
            )
        except TimeoutError:
            raise
        except OSError as exc:
            return [], [f"{repo}: git ls-files could not run for {repo_dir}: {exc}"]
        if proc.returncode != 0:
            return [], [f"{repo}: git ls-files failed in {repo_dir} (exit={proc.returncode}): {proc.stderr.decode('utf-8', 'replace').strip()}"]
        files = sorted(rel for rel in proc.stdout.decode("utf-8", "replace").split("\0") if rel and (repo_dir / rel).is_file())
        return (files, []) if files else ([], [f"{repo}: git ls-files returned zero tracked files in {repo_dir}"])
    found: list[str] = []
    for dpath, dnames, fnames in os.walk(repo_dir):
        dnames[:] = sorted(n for n in dnames if n not in _SKIP_PARTS and not n.endswith(".egg-info"))
        found.extend((Path(dpath) / fn).relative_to(repo_dir).as_posix() for fn in sorted(fnames))
    return (sorted(found), []) if found else ([], [f"{repo}: repository directory has zero files: {repo_dir}"])

def _in_scope(repo: str, rel: str) -> bool:
    if not rel.endswith(".py") or any(part in _SKIP_TESTS for part in rel.split("/")[:-1]):
        return False
    if repo == HUB_REPO:
        return rel == "install.py" or (rel.startswith(".github/scripts/") and not rel.startswith(".github/scripts/tests/"))
    return any(rel == scope or rel.startswith(scope.rstrip("/") + "/") for scope in PRODUCTION_PYTHON_SCOPES.get(repo, ()))

def _docstring_nodes(tree: ast.AST) -> set[int]:
    return {
        id(n.body[0].value) for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str)
    }

def _attr_chain(node: ast.Attribute) -> str | None:
    parts, cur = [node.attr], node.value
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    return ".".join(reversed([*parts, cur.id])) if isinstance(cur, ast.Name) else None

def _abi_identifier(repo_dir: Path, rel: str) -> tuple[str | None, str | None, str | None]:
    path = repo_dir / rel
    try:
        tree = ast.parse(path.read_bytes(), filename=str(path))
    except TimeoutError:
        raise
    except (OSError, SyntaxError) as exc:
        return None, None, f"cannot parse {rel}: {exc}"
    first = tree.body[0] if tree.body else None
    if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)):
        return None, None, "missing module docstring with Upstream-ABI"
    match = _ABI_RE.search(first.value.value)
    marker_line = first.lineno + (first.value.value[: match.start()].count("\n") if match else 0)
    symbol = match.group(1) if match else ""
    final = re.split(r"[/:.]", symbol)[-1] if symbol else ""
    if (first.lineno > 35 or not match or marker_line > 35 or not _ABI_ID_RE.fullmatch(symbol)
            or symbol.lower() in _ABI_GENERIC or final.lower() in _ABI_GENERIC or re.fullmatch(r"v\d+", final.lower())):
        return None, None, "missing distinct, non-generic 'Upstream-ABI: <symbol>' header"
    docs, idents, strings = _docstring_nodes(tree), set(), []
    for node in ast.walk(tree):
        if id(node) in docs:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.append(node.value)
        elif isinstance(node, ast.Name):
            idents.add(node.id)
        elif isinstance(node, ast.Attribute):
            idents.add(node.attr)
            if dotted := _attr_chain(node):
                idents.add(dotted)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            idents.add(node.name)
        elif isinstance(node, ast.alias):
            for part in filter(None, (node.name, node.asname)):
                idents.update((part, *part.split(".")))
        elif isinstance(node, ast.arg):
            idents.add(node.arg)
    for sym in (symbol, *([final] if len(final) >= 4 and final != symbol else [])):
        if sym in idents or any(re.search(rf"(?<![A-Za-z0-9_]){re.escape(sym)}(?![A-Za-z0-9_])", s) for s in strings):
            return symbol, sym, None
    return None, None, f"Upstream-ABI symbol {symbol!r} is not referenced by non-docstring AST"

def _check_names(repo: str, repo_dir: Path, tracked: Sequence[str], candidates: Sequence[str],
                 external_importers: Mapping[str, set[str]]) -> list[str]:
    errors, tracked_set, cand_set, families_seen = [], set(tracked), set(candidates), set()
    for rel in candidates:
        path = Path(rel)
        stem, parent = path.stem, path.parent.as_posix()
        if _LEGACY_STEM_RE.match(stem):
            errors.append(f"{repo}: legacy/shadow production module {rel} must be deleted or renamed")
            continue
        copy_base = None if not (copy := _COPY_STEM_RE.match(stem)) else (f"{parent}/{copy.group(1)}.py" if parent != "." else f"{copy.group(1)}.py")
        if copy_base and copy_base in tracked_set:
            errors.append(f"{repo}: shadow copy {rel} coexists with {Path(copy_base).name} in {parent}/")
            continue
        if not (version := _VERSION_STEM_RE.match(stem)):
            continue
        base = version.group("base")
        base_rel = f"{parent}/{base}.py" if parent != "." else f"{base}.py"
        family = [o for o in candidates if Path(o).parent.as_posix() == parent and (m := _VERSION_STEM_RE.match(Path(o).stem)) and m.group("base") == base]
        if (base_rel not in cand_set and len(family) <= 1) or (parent, base) in families_seen:
            continue
        families_seen.add((parent, base))
        family_set, seen_keys = set(family), {}
        for member in sorted(family):
            identifier, bound_sym, failure = _abi_identifier(repo_dir, member)
            outside = external_importers.get(member, set()) - family_set
            if failure:
                errors.append(f"{repo}: shadow/versioned module {member} requires either deleting superseded versions or declaring a distinct, AST-grounded 'Upstream-ABI: <symbol>' header ({failure})")
            elif not outside:
                errors.append(f"{repo}: versioned module {member} has no reachable caller outside its version family")
            elif identifier in seen_keys or (bound_sym and bound_sym in seen_keys):
                prev = seen_keys.get(identifier) or seen_keys[bound_sym]
                errors.append(f"{repo}: versioned module {member} duplicates Upstream-ABI binding {bound_sym!r} from {prev}; each version needs a distinct ABI symbol")
            else:
                seen_keys[identifier] = member
                if bound_sym:
                    seen_keys[bound_sym] = member
    return errors

def _pyproject_metadata(repo_dir: Path) -> tuple[list[tuple[str, str]], list[str]]:
    aliases, entries = [], []
    for rel in ("pyproject.toml", "plugins/mindie-agent/pyproject.toml"):
        path = repo_dir / rel
        if not path.is_file():
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except TimeoutError:
            raise
        except (OSError, ValueError):
            continue
        base, tool, project = Path(rel).parent, data.get("tool") or {}, data.get("project") or {}
        hatch = ((tool.get("hatch") or {}).get("build") or {}).get("targets", {}).get("wheel", {}).get("sources")
        if isinstance(hatch, dict):
            aliases.extend((posixpath.normpath((base / s).as_posix()), d.strip("/").replace("/", ".")) for s, d in hatch.items() if isinstance(s, str) and isinstance(d, str))
        elif isinstance(hatch, list):
            aliases.extend((posixpath.normpath((base / s).as_posix()), "") for s in hatch if isinstance(s, str))
        if isinstance(pkg_dir := (tool.get("setuptools") or {}).get("package-dir"), dict):
            aliases.extend((posixpath.normpath((base / d).as_posix()), s.strip("/").replace("/", ".")) for s, d in pkg_dir.items() if isinstance(s, str) and isinstance(d, str))
        for key in ("scripts", "gui-scripts"):
            entries.extend(v for v in (project.get(key) or {}).values() if isinstance(v, str))
        for group in (project.get("entry-points") or {}).values():
            if isinstance(group, dict):
                entries.extend(v for v in group.values() if isinstance(v, str))
    return aliases, entries

def _module_identity(rel: str, aliases: Sequence[tuple[str, str]], init_dirs: set[str]) -> tuple[str, set[str]]:
    parts = rel[:-3].split("/")
    is_init, parent_dir = parts[-1] == "__init__", "/".join(parts[:-1]) or "."
    base = parts[:-1] if is_init else parts
    names, primary = set(), ""
    for prefix, package in aliases:
        p_parts = [] if prefix in {"", "."} else [p for p in prefix.strip("/").split("/") if p]
        if base[: len(p_parts)] == p_parts and (mapped := ".".join(([package] if package else []) + base[len(p_parts) :])) and not mapped.startswith("."):
            names.add(mapped)
            primary = primary or mapped
    if base and base[0] == "src" and "src" not in init_dirs and (src_mod := ".".join(base[1:])) and not src_mod.startswith("."):
        names.add(src_mod)
        primary = primary or src_mod
    for sroot in _SCRIPT_IMPORT_ROOTS:
        s_parts = sroot.split("/")
        if sroot not in init_dirs and base[: len(s_parts)] == s_parts and len(base) > len(s_parts):
            s_mod = ".".join(base[len(s_parts) :])
            names.add(s_mod)
            primary = primary or s_mod
    if (raw_mod := ".".join(base)) and not any(part.startswith(".") for part in base):
        names.add(raw_mod)
        primary = primary or raw_mod
    if not is_init and parent_dir not in init_dirs and parent_dir in {".", *_SCRIPT_IMPORT_ROOTS} and base:
        names.add(base[-1])
        primary = primary or base[-1]
    return primary, {n for n in names if n and not n.endswith(".__init__") and n != "__init__"}

def _is_positive_main_expr(expr: ast.expr) -> bool:
    if isinstance(expr, ast.BoolOp) and isinstance(expr.op, ast.And):
        return any(_is_positive_main_expr(v) for v in expr.values)
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and isinstance(expr.ops[0], ast.Eq) and len(expr.comparators) == 1:
        a, b = expr.left, expr.comparators[0]
        return (isinstance(a, ast.Name) and a.id == "__name__" and isinstance(b, ast.Constant) and b.value == "__main__"
                or isinstance(b, ast.Name) and b.id == "__name__" and isinstance(a, ast.Constant) and a.value == "__main__")
    return False

def _has_main_guard(tree: ast.Module) -> bool:
    return any(isinstance(stmt, ast.If) and _is_positive_main_expr(stmt.test) for stmt in tree.body)

def _path_call_parts(call: ast.Call) -> tuple[list[str], set[int]] | None:
    fn = call.func
    if not ((isinstance(fn, ast.Name) and fn.id in _PATH_CTORS) or (isinstance(fn, ast.Attribute) and fn.attr in _PATH_CTORS)) or not call.args or call.keywords:
        return None
    parts, used = [], set()
    for arg in call.args:
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            return None
        used.add(id(arg))
        parts.append(arg.value.strip("/"))
    return parts, used

def _div_chain(node: ast.BinOp) -> tuple[str | None, set[int]]:
    parts, consumed, cur = [], set(), node
    while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.Div):
        if not (isinstance(cur.right, ast.Constant) and isinstance(cur.right.value, str)):
            return None, set()
        consumed.add(id(cur.right))
        parts.append(cur.right.value.strip("/"))
        cur = cur.left
    parts.reverse()
    if isinstance(cur, ast.Constant) and isinstance(cur.value, str):
        consumed.add(id(cur))
        parts = [cur.value.strip("/"), *parts]
    elif isinstance(cur, ast.Call) and (cp := _path_call_parts(cur)) is not None:
        consumed |= cp[1]
        parts = [*cp[0], *parts]
    joined = "/".join(part for part in parts if part)
    return (joined, consumed) if joined.endswith(".py") else (None, set())

def _check_python_graph(repo: str, repo_dir: Path, tracked: Sequence[str], candidates: Sequence[str]) -> list[str]:
    py_files = [rel for rel in tracked if rel.endswith(".py")]
    if not py_files:
        return _check_names(repo, repo_dir, tracked, candidates, {})
    errors, tracked_set, cand_set = [], set(tracked), set(candidates)
    by_name: dict[str, list[str]] = {}
    for rel in py_files:
        by_name.setdefault(Path(rel).name, []).append(rel)
    aliases, entries = _pyproject_metadata(repo_dir)
    init_dirs = {rel[: -len("/__init__.py")] for rel in py_files if rel.endswith("/__init__.py")} | ({"."} if "__init__.py" in tracked_set else set())
    module_map, primary = {}, {}
    for rel in py_files:
        prim, names = _module_identity(rel, aliases, init_dirs)
        primary[rel] = prim
        for name in names:
            module_map.setdefault(name, set()).add(rel)

    def resolve(name: str, *, caller_rel: str | None = None) -> set[str]:
        direct = set(module_map.get(name, ()))
        if not direct and caller_rel and "." not in name and Path(caller_rel).name != "__init__.py":
            c_parent = Path(caller_rel).parent.as_posix()
            if any(c_parent == sr or c_parent.startswith(sr + "/") for sr in _SCRIPT_IMPORT_ROOTS) and (sib := f"{c_parent}/{name}.py") in tracked_set:
                direct.add(sib)
        if not direct:
            return set()
        parts = [p for p in name.split(".") if p]
        for idx in range(1, len(parts)):
            direct |= module_map.get(".".join(parts[:idx]), set())
        return direct

    def resolve_py_path(owner_rel: str, raw_path: str, *, allow_unique_name: bool = True) -> set[str]:
        clean = re.sub(r"^(?:\./)+", "", raw_path.strip().replace("\\", "/"))
        if not clean.endswith(".py"):
            return set()
        if hits := {n for pfx in (Path(owner_rel).parent.as_posix(), ".") if (n := posixpath.normpath(f"{pfx}/{clean}")) in tracked_set}:
            return hits
        if allow_unique_name and "/" not in clean and len(matches := by_name.get(clean, ())) == 1:
            return {matches[0]}
        if "/" in clean and not clean.startswith("../") and len(matches := [p for p in py_files if p.endswith("/" + clean)]) == 1:
            return {matches[0]}
        return set()

    entry_roots = {item for entry in entries for item in resolve(entry.split(":", 1)[0].strip())}
    roots, external_importers = set(entry_roots), {r: {"<entrypoint>"} for r in entry_roots}
    for rel in py_files:
        name = Path(rel).name
        if name in {"__main__.py", "conftest.py"} or rel == "install.py" or (name == "__init__.py" and Path(rel).parent.parent.as_posix() not in init_dirs):
            roots.add(rel)
        if rel not in cand_set and (any(part in _SKIP_TESTS for part in rel.split("/")[:-1])
                or (rel.startswith("scripts/") and "scripts" not in PRODUCTION_PYTHON_SCOPES.get(repo, ()))):
            roots.add(rel)

    for rel in tracked:
        suffix, top = Path(rel).suffix, rel.split("/", 1)[0]
        if suffix not in _MANIFEST_SUFFIXES or top in _MANIFEST_SKIP_DIRS or Path(rel).name in _HISTORICAL_ROOT_DOCS:
            continue
        try:
            path = repo_dir / rel
            text = ("" if suffix == ".json" and path.stat().st_size > 256 * 1024 else path.read_text(encoding="utf-8", errors="replace")).replace("\\", "/")
        except TimeoutError:
            raise
        except OSError:
            continue
        m_hits = {h for m in re.finditer(r"(?<![\w.-])((?:\.{1,2}/)?[A-Za-z0-9_@.+/-]+\.py)\b", text) for h in resolve_py_path(rel, m.group(1), allow_unique_name=False)}
        for pattern in (r"(?:^|[\s\"'])-m[ \t]+([A-Za-z_][\w.]*)", r'"-m"\s*,\s*"([A-Za-z_][\w.]*)"',
                        r"\b(?:import|from)[ \t]+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\b",
                        r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+):([A-Za-z_]\w*)", r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*){2,})\b"):
            for match in re.finditer(pattern, text):
                m_hits |= resolve(match.group(1))
        roots |= m_hits
        for h in m_hits:
            external_importers.setdefault(h, set()).add(f"<manifest:{rel}>")

    edges: dict[str, set[str]] = {}
    for rel in py_files:
        try:
            node = ast.parse((repo_dir / rel).read_bytes(), filename=rel)
        except TimeoutError:
            raise
        except (OSError, SyntaxError) as exc:
            if rel in cand_set:
                errors.append(f"{repo}: cannot parse production Python module {rel}: {exc}")
            continue
        if _has_main_guard(node):
            roots.add(rel)
        target, docs, consumed = set(), _docstring_nodes(node), set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Div):
                joined, used = _div_chain(sub)
                if joined is not None:
                    consumed |= used
                    target |= resolve_py_path(rel, joined)
            elif isinstance(sub, ast.Call) and (cp := _path_call_parts(sub)) is not None and (joined := "/".join(p for p in cp[0] if p)).endswith(".py"):
                consumed |= cp[1]
                target |= resolve_py_path(rel, joined)
        package = primary[rel] if Path(rel).name == "__init__.py" else (primary[rel].rsplit(".", 1)[0] if "." in primary[rel] else "")
        for sub in ast.walk(node):
            if isinstance(sub, ast.Import):
                for alias in sub.names:
                    parts = alias.name.split(".")
                    for idx in range(1, len(parts) + 1):
                        target |= resolve(".".join(parts[:idx]), caller_rel=rel)
            elif isinstance(sub, ast.ImportFrom):
                base = sub.module or ""
                if sub.level:
                    try:
                        base = importlib.util.resolve_name("." * sub.level + base, package) if package else ""
                    except ValueError:
                        base = ""
                for alias in sub.names:
                    target |= resolve(".".join(filter(None, [base, alias.name])), caller_rel=rel) or (resolve(base, caller_rel=rel) if base else set())
            elif isinstance(sub, ast.Call):
                func = sub.func
                if (isinstance(func, ast.Name) and func.id in {"import_module", "__import__"}
                        or isinstance(func, ast.Attribute) and func.attr == "import_module") and sub.args:
                    if isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str):
                        mod_arg = sub.args[0].value
                        if mod_arg.startswith("."):
                            try:
                                mod_arg = importlib.util.resolve_name(mod_arg, package) if package else ""
                            except ValueError:
                                mod_arg = ""
                        if mod_arg:
                            target |= resolve(mod_arg, caller_rel=rel)
            elif isinstance(sub, ast.Constant) and isinstance(sub.value, str) and id(sub) not in docs and id(sub) not in consumed:
                value = sub.value.strip()
                if re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", value):
                    target |= resolve(value, caller_rel=rel)
                if value.endswith(".py"):
                    target |= resolve_py_path(rel, value)
        for p_dir in (Path(rel).parent, *Path(rel).parents):
            init_rel = f"{p_dir.as_posix()}/__init__.py" if p_dir.as_posix() != "." else "__init__.py"
            if init_rel in tracked_set and init_rel != rel:
                target.add(init_rel)
        edges[rel] = target

    reached, stack = set(roots), list(roots)
    while stack:
        cur = stack.pop()
        for nxt in edges.get(cur, ()):
            external_importers.setdefault(nxt, set()).add(cur)
            if nxt not in reached:
                reached.add(nxt)
                stack.append(nxt)
    errors.extend(_check_names(repo, repo_dir, tracked, candidates, external_importers))
    suffix = " is unreachable from __init__/__main__/install/entrypoint/test/manifest/launcher roots"
    errors.extend(f"{repo}: unreferenced production module {rel}{suffix}" for rel in sorted(cand_set - reached))
    return errors

def _mask(text: str) -> str:
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    chars = list(norm)
    for m in re.finditer(r"<!--.*?-->", norm, re.DOTALL):
        s, e = m.span()
        chars[s:e] = ["\n" if c == "\n" else " " for c in chars[s:e]]
    lines, f_char, f_len = "".join(chars).split("\n"), "", 0
    for idx, line in enumerate(lines):
        if f_char:
            s = line.lstrip(" \t")
            if len(line) - len(s) <= 3 and s.rstrip(" \t") and set(s.rstrip(" \t")) == {f_char} and len(s.rstrip(" \t")) >= f_len:
                f_char, f_len = "", 0
            lines[idx] = " " * len(line)
        elif (m := _FENCE_OPEN_RE.match(line)) and (m.group(1)[0] == "~" or "`" not in m.group(2)):
            f_char, f_len = m.group(1)[0], len(m.group(1))
            lines[idx] = " " * len(line)
    return "\n".join(lines)

def _slug_variants(heading: str) -> set[str]:
    clean = re.sub(r"<[^>]+>", "", re.sub(r"\s*\{#[A-Za-z0-9_:-]+\}\s*$", "", heading)).strip()
    clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean).replace("`", "").replace("**", "").replace("*", "").lower()
    without = re.sub(r"[^\w\s-]", "", clean).replace(" ", "-")
    with_emoji = re.sub(r"[^\w\s\ufe0f-]", "", clean).replace(" ", "-")
    return {without, with_emoji, without.strip("-"), with_emoji.strip("-")}

def _anchors(text: str) -> set[str]:
    masked = _mask(text)
    explicit = set(_HEADING_CUSTOM_ID_RE.findall(masked)) | {s.strip() for s in re.findall(r'\b(?:id|name)=["\']([^"\']+)["\']', masked)}
    anchors, occupied, counts = set(explicit), set(explicit), {}
    for match in re.finditer(r"^[ \t]{0,3}#{1,6}\s+(.+?)\s*$", masked, re.MULTILINE):
        for slug in _slug_variants(match.group(1)):
            if not slug:
                continue
            idx = counts.get(slug, 0)
            cand = slug if idx == 0 else f"{slug}-{idx}"
            while cand in occupied:
                idx += 1
                cand = f"{slug}-{idx}"
            counts[slug] = idx + 1
            occupied.add(cand)
            anchors.add(cand)
    return anchors

def _anchor_matches(fragment: str, anchors: set[str]) -> bool:
    clean = fragment.replace("\ufe0f", "")
    return fragment in anchors or clean in anchors

def _links(masked: str) -> Iterable[str]:
    for match in re.finditer(r"!?\[[^\]]*\]\(([^)\n]*)\)", masked):
        parts = match.group(1).strip().split()
        yield parts[0].strip("<>") if parts else ""
    for match in re.finditer(r"(?:href|src)=[\"']([^\"']*)[\"']", masked):
        yield match.group(1).strip()

def _active_docs(tracked: Sequence[str]) -> list[str]:
    return [rel for rel in tracked if rel.endswith(".md") and not rel.startswith(_DOC_SKIP_PREFIXES)
            and (rel.startswith("docs/") or ("/" not in rel and (rel == "AGENTS.md" or rel.startswith(("README", "CONTRIBUTING")))))]

def _tracked_inventory_sets(tracked: Sequence[str]) -> tuple[set[str], set[str]]:
    dirs: set[str] = {"."}
    for rel in tracked:
        parts = rel.split("/")[:-1]
        dirs.update("/".join(parts[:idx]) for idx in range(1, len(parts) + 1))
    return set(tracked), dirs

def _check_links(repo: str, repo_dir: Path, tracked: Sequence[str], docs: Sequence[str], siblings: Mapping[str, Path]) -> list[str]:
    errors, sibling_sets, anchor_cache = [], {}, {}
    tracked_set, tracked_dirs = _tracked_inventory_sets(tracked)
    strict_prefixes = set(PRODUCTION_PYTHON_SCOPES.get(repo, ())) | {".github/scripts", ".github/workflows", "channels"}
    aux_prefixes = {"scripts", ".claude-plugin", ".codex-plugin", "plugins/mindie-agent"}

    def file_anchors(p: Path) -> set[str] | None:
        if p not in anchor_cache:
            try:
                anchor_cache[p] = _anchors(p.read_text(encoding="utf-8", errors="replace"))
            except TimeoutError:
                raise
            except OSError:
                return None
        return anchor_cache[p]

    for doc_rel in docs:
        try:
            text = (repo_dir / doc_rel).read_text(encoding="utf-8", errors="replace")
        except TimeoutError:
            raise
        except OSError as exc:
            errors.append(f"{repo}: cannot read active document {doc_rel}: {exc}")
            continue
        masked, own_anchors, doc_parent = _mask(text), _anchors(text), Path(doc_rel).parent.as_posix()
        for raw_link in _links(masked):
            if not raw_link:
                errors.append(f"{repo}: {doc_rel}: empty link destination")
                continue
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw_link) or raw_link.startswith("//"):
                continue
            before_frag, has_frag, raw_frag = raw_link.partition("#")
            fragment = urllib.parse.unquote(raw_frag) if has_frag else ""
            target = urllib.parse.unquote(before_frag.partition("?")[0])
            if not target:
                if fragment and not _anchor_matches(fragment, own_anchors):
                    errors.append(f"{repo}: {doc_rel}: broken internal anchor #{fragment}")
                continue
            rel_expr = f"{repo}/{target.lstrip('/')}" if target.startswith("/") else (f"{repo}/{doc_parent}/{target}" if doc_parent != "." else f"{repo}/{target}")
            comp = posixpath.normpath(rel_expr).split("/")
            target_repo_dir, target_rel = None, None
            if comp and comp[0] == repo:
                target_repo_dir, target_rel, t_files, t_dirs = repo_dir, "/".join(comp[1:]) or ".", tracked_set, tracked_dirs
            elif comp and comp[0] in ALL_KNOWN_REPOS:
                if (sib_dir := siblings.get(comp[0])) is None:
                    continue
                if comp[0] not in sibling_sets:
                    sibling_sets[comp[0]] = _tracked_inventory_sets(_tracked(sib_dir, comp[0])[0])
                target_repo_dir, target_rel = sib_dir, "/".join(comp[1:]) or "."
                t_files, t_dirs = sibling_sets[comp[0]]
            if target_repo_dir is None or target_rel is None:
                errors.append(f"{repo}: {doc_rel}: broken relative link {raw_link!r}")
                continue
            if target_rel not in t_files and target_rel not in t_dirs and "." not in Path(target_rel).name and f"{target_rel}.md" in t_files:
                target_rel = f"{target_rel}.md"
            if target_rel not in t_files and target_rel not in t_dirs:
                errors.append(f"{repo}: {doc_rel}: broken relative link {raw_link!r}")
                continue
            if fragment and target_rel in t_files and target_rel.lower().endswith(".md"):
                if (anc := file_anchors(target_repo_dir / target_rel)) is not None and not _anchor_matches(fragment, anc):
                    errors.append(f"{repo}: {doc_rel}: broken anchor #{fragment} in {raw_link!r}")

        for match in re.finditer(r"`([^`\n]+)`", masked):
            token = re.sub(r"(?::L?\d+(?:-\d+)?|#L\d+(?:-\d+)?)$", "", match.group(1).strip())
            if "/" not in token or " " in token or any(c in token for c in "<>*?{}[]$|") or token.startswith(("http", "/", "~", "#")):
                continue
            if Path(token).suffix.lower() not in _INLINE_PATH_SUFFIXES:
                continue
            candidates_rel = [posixpath.normpath(f"{b}/{token}" if b != "." else token) for b in (doc_parent, ".", "plugins/mindie-agent")]
            if any(cand in tracked_set for cand in candidates_rel):
                continue
            for cand in candidates_rel:
                if cand.startswith("../"):
                    continue
                parent = Path(cand).parent.as_posix()
                if any(cand == p or cand.startswith(p.rstrip("/") + "/") for p in strict_prefixes) or (
                        parent in tracked_dirs and any(parent == p or parent.startswith(p + "/") for p in aux_prefixes)):
                    errors.append(f"{repo}: {doc_rel}: inline code path {token!r} does not exist")
                    break
    return errors

def _resolved_doc_targets(text: str, doc_rel: str) -> set[str]:
    doc_parent, targets = Path(doc_rel).parent.as_posix(), set()
    for raw in _links(_mask(text)):
        if not raw or raw.startswith(("#", "//")) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw):
            continue
        if clean := urllib.parse.unquote(raw.partition("#")[0].partition("?")[0]).rstrip("/"):
            targets.add(posixpath.normpath(clean.lstrip("/") if clean.startswith("/") else (f"{doc_parent}/{clean}" if doc_parent != "." else clean)))
    return targets

def _check_hub_release_index(repo_dir: Path, tracked: set[str]) -> list[str]:
    channel = repo_dir / "channels/0.1.json"
    required = ("docs/README.md", "docs/README.en.md", "README.md", "README.en.md")
    if "channels/0.1.json" not in tracked or not channel.is_file() or any(rel not in tracked for rel in required):
        return []
    try:
        manifest = json.loads(channel.read_text(encoding="utf-8"))
    except TimeoutError:
        raise
    except (OSError, ValueError) as exc:
        return [f"{HUB_REPO}: failed parsing channels/0.1.json: {exc}"]
    entries = [item for item in (manifest.get("patch_releases") or []) if isinstance(item, dict) and item.get("patch_version")]
    published = [str(item["patch_version"]) for item in entries if item.get("status") != "failed_unpublished"]
    unpublished = [str(item["patch_version"]) for item in entries if item.get("status") == "failed_unpublished"]
    if not published:
        return []
    errors: list[str] = []
    doc_links = {rel: _resolved_doc_targets((repo_dir / rel).read_text(encoding="utf-8"), rel) for rel in required}
    for version in published:
        for suffix in (".md", ".en.md"):
            target = f"docs/releases/{version}{suffix}"
            if target not in tracked:
                errors.append(f"{HUB_REPO}: published channel release {version} is missing {target}")
                continue
            for readme in ("docs/README.md", "docs/README.en.md"):
                if target not in doc_links[readme]:
                    errors.append(f"{HUB_REPO}: {readme} does not link published release {target}")
    latest = published[-1]
    latest_targets = {f"docs/releases/{latest}.md", f"docs/releases/{latest}.en.md"}
    for readme in ("README.md", "README.en.md"):
        if not (doc_links[readme] & latest_targets):
            errors.append(f"{HUB_REPO}: {readme} does not link latest published channel release {latest}")
    for version in unpublished:
        bad_targets = {f"docs/releases/{version}.md", f"docs/releases/{version}.en.md"}
        for readme in required:
            if doc_links[readme] & bad_targets:
                errors.append(f"{HUB_REPO}: {readme} must not list failed_unpublished release {version}")
    return errors

def _lang_tag(rel: str) -> str:
    return "en" if rel.endswith(".en.md") else ("zh" if rel.endswith(".zh.md") else "base")

def _counterpart(rel: str, candidate_md_files: Sequence[str]) -> str | None:
    lang = _lang_tag(rel)
    if lang == "en":
        sibling, allowed = rel[: -len(".en.md")], (".md", ".zh.md")
    elif lang == "zh":
        sibling, allowed = rel[: -len(".zh.md")], (".md", ".en.md")
    else:
        return None
    candidate_set = set(candidate_md_files)
    for suffix in allowed:
        if sibling + suffix in candidate_set:
            return sibling + suffix
    if Path(rel).parent.as_posix() not in {".", "docs"}:
        return None
    normalized = re.sub(r"[^a-z0-9]", "", Path(sibling).name.lower())
    matches = [other for other in candidate_md_files
               if other != rel and ("/" in rel) != ("/" in other) and Path(other).parent.as_posix() in {".", "docs"}
               and _lang_tag(other) != lang and re.sub(r"[^a-z0-9]", "", re.sub(r"\.(?:en|zh)$", "", Path(other).stem.lower())) == normalized]
    return matches[0] if len(matches) == 1 else None

def _check_docs(repo: str, repo_dir: Path, tracked: Sequence[str]) -> list[str]:
    errors: list[str] = []
    if repo in CODE_DOC_HYGIENE_FLOOR_VERSIONS or repo == HUB_REPO:
        required = ["README.md", "README.en.md", *(["CONTRIBUTING.md", "CONTRIBUTING.en.md", "docs/README.md", "docs/README.en.md"] if repo == HUB_REPO else [])]
        errors.extend(f"{repo}: required bilingual living document {rel} is missing" for rel in required if rel not in tracked or not (repo_dir / rel).is_file())
    active_set = set(_active_docs(tracked))
    candidates = [r for r in tracked if r.endswith(".md") and not r.startswith(_DOC_SKIP_PREFIXES) and ("/" not in r or r.startswith("docs/")) and r not in _HISTORICAL_ROOT_DOCS]
    paired: set[tuple[str, str]] = set()
    for rel in candidates:
        if not rel.endswith((".en.md", ".zh.md")):
            continue
        partner = _counterpart(rel, candidates)
        if partner is None:
            if rel in active_set:
                errors.append(f"{repo}: bilingual document {rel} is missing its tracked counterpart")
        elif rel in active_set or partner in active_set:
            paired.add((partner, rel) if partner <= rel else (rel, partner))
    for left, right in sorted(paired):
        try:
            left_count = len(re.findall(r"^[ \t]{0,3}##\s+", _mask((repo_dir / left).read_text(encoding="utf-8")), re.MULTILINE))
            right_count = len(re.findall(r"^[ \t]{0,3}##\s+", _mask((repo_dir / right).read_text(encoding="utf-8")), re.MULTILINE))
        except TimeoutError:
            raise
        except OSError as exc:
            errors.append(f"{repo}: cannot read bilingual pair {left} / {right}: {exc}")
            continue
        if left_count != right_count:
            errors.append(f"{repo}: bilingual H2 section mismatch {left} ({left_count}) vs {right} ({right_count})")
    return errors

def _plan_targets(
    siblings_roots: Sequence[Path], *, main_repo: Path | None, require_siblings: bool,
    required_repos: Sequence[str], explicit_repos: Mapping[str, Path] | None, enforce_all: bool,
) -> tuple[list[str], list[tuple[str, Path]], list[str], list[str]]:
    errors, required, targets, missing, selected = [], list(dict.fromkeys(required_repos)), [], [], []
    def mark_missing(name: str, err: str | None = None) -> None:
        selected.append(name)
        missing.append(name)
        if err:
            errors.append(err)
    if main_repo is not None or bool(explicit_repos and HUB_REPO in explicit_repos) or enforce_all or HUB_REPO in required:
        if main_repo is not None or (explicit_repos and HUB_REPO in explicit_repos):
            hub_dir = Path((explicit_repos or {}).get(HUB_REPO, main_repo)).expanduser().resolve()
            (selected.append(HUB_REPO), targets.append((HUB_REPO, hub_dir))) if hub_dir.is_dir() else mark_missing(HUB_REPO, f"{HUB_REPO}: repository directory not found: {hub_dir}")
        else:
            mark_missing(HUB_REPO, f"{HUB_REPO}: {'--enforce-all requires an explicit main repository' if enforce_all else '--release-repo requires --main-repo or --repo mindie-agent=/abs/path'}")
    pool = list(dict.fromkeys([*CODE_DOC_HYGIENE_FLOOR_VERSIONS, *(n for n in required if n != HUB_REPO)])) if enforce_all else (
        list(CODE_DOC_HYGIENE_FLOOR_VERSIONS) if not required else [n for n in required if n != HUB_REPO])
    for name in pool:
        if name not in ALL_KNOWN_REPOS:
            mark_missing(name, f"{name}: unknown repository in --release-repo")
            continue
        try:
            repo_dir = resolve_repo(name, siblings_roots, explicit_repos=explicit_repos)
        except ValueError as exc:
            mark_missing(name, str(exc))
            continue
        if repo_dir is None:
            need = enforce_all or name in required or (require_siblings and name not in _INDEPENDENT_EXEMPT)
            label = "sibling checkout" if name in CODE_DOC_HYGIENE_FLOOR_VERSIONS else "selected release checkout"
            mark_missing(name, f"{name}: {label} not found in {list(siblings_roots)} for code/doc hygiene gate" if need else None)
            continue
        ver, ver_err = (None, None) if (enforce_all or name in required or name not in CODE_DOC_HYGIENE_FLOOR_VERSIONS) else _version(repo_dir, name)
        if ver_err:
            selected.append(name)
            errors.append(ver_err)
        elif enforce_all or name in required or name not in CODE_DOC_HYGIENE_FLOOR_VERSIONS or (ver is not None and ver >= CODE_DOC_HYGIENE_FLOOR_VERSIONS[name]):
            selected.append(name)
            targets.append((name, repo_dir))
    return selected, targets, missing, errors

def verify_code_doc_hygiene(siblings_roots: Sequence[Path], *, main_repo: Path | None = None, require_siblings: bool = False,
                            required_repos: Sequence[str] = (), explicit_repos: Mapping[str, Path] | None = None, enforce_all: bool = False) -> list[str]:
    """Verify lean Python filenames/import graphs and living-doc hygiene for selected repositories."""
    _, targets, _, errors = _plan_targets(siblings_roots, main_repo=main_repo, require_siblings=require_siblings, required_repos=required_repos, explicit_repos=explicit_repos, enforce_all=enforce_all)
    siblings: dict[str, Path] = {HUB_REPO: Path((explicit_repos or {}).get(HUB_REPO, main_repo)).expanduser().resolve()} if (main_repo is not None or (explicit_repos and HUB_REPO in explicit_repos)) else {}
    for name in (n for n in ALL_KNOWN_REPOS if n != HUB_REPO):
        try:
            if (found := resolve_repo(name, siblings_roots, explicit_repos=explicit_repos)) is not None:
                siblings[name] = found
        except ValueError:
            continue
    seen: set[str] = set()
    for repo, repo_dir in targets:
        if repo in seen:
            continue
        seen.add(repo)
        tracked, inventory_errors = _tracked(repo_dir, repo)
        errors.extend(inventory_errors)
        if tracked:
            candidates = [rel for rel in tracked if _in_scope(repo, rel)]
            errors.extend([*_check_python_graph(repo, repo_dir, tracked, candidates), *_check_links(repo, repo_dir, tracked, _active_docs(tracked), siblings), *_check_docs(repo, repo_dir, tracked)])
            if repo == HUB_REPO:
                errors.extend(_check_hub_release_index(repo_dir, set(tracked)))
    return errors

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--siblings-root", type=Path, action="append", default=[])
    parser.add_argument("--repo", action="append", default=[], metavar="NAME=/ABS/PATH")
    parser.add_argument("--require-siblings", action="store_true")
    parser.add_argument("--release-repo", action="append", default=[])
    parser.add_argument("--enforce-all", action="store_true")
    args = parser.parse_args(argv)
    try: explicit_repos = parse_repo_overrides(args.repo)
    except ValueError as exc:
        print(f"[code-doc-hygiene:FAIL] {exc}", file=sys.stderr)
        return 1
    main_repo = args.main_repo.resolve()
    roots = infer_default_siblings_roots(main_repo, args.siblings_root)
    kw = dict(main_repo=main_repo, require_siblings=args.require_siblings, required_repos=args.release_repo, explicit_repos=explicit_repos, enforce_all=args.enforce_all)
    selected, targets, missing, _ = _plan_targets(roots, **kw)
    sel_t, ex_t, miss_t = tuple(dict.fromkeys(selected)), tuple(dict.fromkeys(r for r, _ in targets)), tuple(dict.fromkeys(missing))
    print(RepoCoverage(sel_t, ex_t, miss_t, tuple(r for r in ALL_KNOWN_REPOS if r not in sel_t)).format_line("code-doc-hygiene"))
    if errors := verify_code_doc_hygiene(roots, **kw):
        print("\n".join(f"[code-doc-hygiene:FAIL] {err}" for err in errors), file=sys.stderr)
        return 1
    print("[code-doc-hygiene:OK] Lean code and bilingual living-doc hygiene verified.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
