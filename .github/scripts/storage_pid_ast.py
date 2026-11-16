#!/usr/bin/env python3
"""Closed-capability Windows PID safety AST verifier for storage modules (Guardrail P8).

[Role]
Verifies via Python stdlib `ast` that storage lifecycle/lease/GC modules never invoke
`os.kill(pid, 0)` (or any aliased, reflective, submodule-hopped, or subclassed equivalent)
unless guarded by a proven literal POSIX branch.

[Invariants]
- Enforces exact, closed syntactic allowlists verified across all 15 repositories:
  1. Exact module/from-import allowlists (`_ALLOWED_EXACT_IMPORTS`, `_ALLOWED_STDLIB_FROM_PAIRS`)
     plus exact per-stdlib-module attribute allowlists (`_ALLOWED_STDLIB_MOD_ATTRS` and
     `_ALLOWED_OS_PATH_ATTRS`), preventing `os.path.os` submodule hops and unexpected stdlib gadgets.
  2. Bans private `._*` attributes outside `self._*` and local storage modules, restricts dunder
     reads strictly to `{"__init__", "__name__"}` (banning `__class__`, `__dict__`, `__setattr__`,
     etc.), bans class `keywords`, restricts class `bases` to unshadowed safe types, and bans 3-arg
     `type(...)`.
  3. Bans first-class module/`os.path`/`.WinDLL`/`.kill` references, bans indirect callees,
     restricts `.compile(...)` to unshadowed in-scope `re`, and requires every non-exempt
     `<expr>.kill(...)` / `kill(...)` call to sit inside a proven literal POSIX branch.

[Timeouts & Locks]
- Pure in-memory AST traversal; acquires no locks and spawns no subprocesses.

[Side-Effect Policy]
- Strictly read-only inspection of Python source files.
"""

from __future__ import annotations

import ast
from pathlib import Path

_COMPREHENSION_TYPES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_REFLECTIVE_FNS = frozenset(
    {
        "getattr", "setattr", "delattr", "eval", "exec", "compile", "vars", "globals",
        "locals", "attrgetter", "methodcaller", "__import__", "breakpoint",
    }
)
_LOCAL_STORAGE_MODULES = frozenset(
    {
        "_host_exec", "bounded_process", "filesystem", "genstate", "host_pin_refresh",
        "leases", "legacy", "legacy_roots", "lifecycle", "loop.locks", "mindie_knowledge",
        "mindie_knowledge.filesystem", "mindie_knowledge.state_layout",
        "mindie_knowledge.storage", "mindie_knowledge.storage.legacy_roots",
        "mindie_knowledge.storage.lifecycle", "mindie_paths", "paths", "product_contract",
        "remote_state_guard", "storage", "storage_common", "storage_gc", "storage_leases",
        "storage_lifecycle", "storage_reclaim", "storage_releases", "storage_spool",
        "storage_support", "uv_cache",
    }
)
_ALLOWED_EXACT_IMPORTS = _LOCAL_STORAGE_MODULES | {
    "_winapi", "argparse", "ast", "contextlib", "ctypes", "errno",
    "fcntl", "hashlib", "json", "msvcrt", "ntpath", "os", "os.path", "pathlib",
    "plistlib", "re", "select", "shlex", "shutil", "sqlite3", "stat", "subprocess",
    "sys", "tempfile", "threading", "time", "tomllib", "uuid",
}
_ALLOWED_STDLIB_FROM_PAIRS = frozenset(
    {
        ("__future__", "annotations"),
        ("collections.abc", "Iterator"),
        ("contextlib", "ExitStack"),
        ("contextlib", "contextmanager"),
        ("contextlib", "suppress"),
        ("ctypes", "wintypes"),
        ("os", "kill"),
        ("pathlib", "Path"),
        ("urllib.parse", "quote"),
        ("xml.etree", "ElementTree"),
    }
)
_STDLIB_SUBMODULE_IMPORTS: dict[tuple[str, str], str] = {
    ("ctypes", "wintypes"): "wintypes",
    ("xml.etree", "ElementTree"): "ElementTree",
}
_ALLOWED_TYPING_NAMES = frozenset(
    {
        "Any", "Callable", "ClassVar", "Dict", "Final", "FrozenSet", "Generator",
        "IO", "Iterable", "Iterator", "List", "Literal", "Mapping", "MutableMapping",
        "NamedTuple", "NoReturn", "Optional", "Protocol", "Sequence", "Set", "TextIO",
        "Tuple", "TYPE_CHECKING", "TypeAlias", "TypedDict", "Union", "cast", "overload",
    }
)
_ALLOWED_STDLIB_MOD_ATTRS: dict[str, frozenset[str]] = {
    "_winapi": frozenset({"CloseHandle", "GetExitCodeProcess", "OpenProcess", "STILL_ACTIVE"}),
    "ElementTree": frozenset({"ParseError", "fromstring"}),
    "argparse": frozenset({"ArgumentParser"}),
    "ast": frozenset({"Constant", "parse", "walk"}),
    "contextlib": frozenset({"ExitStack", "contextmanager", "suppress"}),
    "ctypes": frozenset(
        {
            "POINTER", "Structure", "WinDLL", "byref", "c_bool", "c_int", "c_long",
            "c_size_t", "c_uint32", "c_uint64", "c_ulong", "c_void_p", "c_wchar",
            "c_wchar_p", "create_unicode_buffer", "get_last_error", "sizeof",
        }
    ),
    "errno": frozenset({"EACCES", "EDEADLK", "EEXIST", "EINVAL", "ENOENT", "EPERM", "ESRCH"}),
    "fcntl": frozenset({"LOCK_EX", "LOCK_NB", "LOCK_SH", "LOCK_UN", "flock"}),
    "hashlib": frozenset({"sha256"}),
    "json": frozenset({"JSONDecodeError", "dump", "dumps", "load", "loads"}),
    "msvcrt": frozenset({"LK_LOCK", "LK_NBLCK", "LK_UNLCK", "locking"}),
    "ntpath": frozenset({"abspath", "normcase", "normpath"}),
    "os": frozenset(
        {
            "O_APPEND", "O_CREAT", "O_EXCL", "O_RDONLY", "O_RDWR", "O_WRONLY",
            "PathLike", "SEEK_SET", "W_OK", "X_OK", "access", "chmod", "close",
            "environ", "fdopen", "fsdecode", "fsencode", "fspath", "fstat", "fsync",
            "getpid", "kill", "listdir", "lseek", "lstat", "makedirs", "mkdir",
            "name", "open", "path", "pathsep", "read", "readlink", "remove", "rename",
            "replace", "rmdir", "scandir", "sep", "stat", "unlink", "utime", "walk", "write",
        }
    ),
    "pathlib": frozenset({"Path", "PurePath", "PosixPath", "WindowsPath"}),
    "plistlib": frozenset({"loads"}),
    "re": frozenset({"IGNORECASE", "compile", "escape", "findall", "fullmatch", "match", "search", "split", "sub"}),
    "select": frozenset({"select"}),
    "shlex": frozenset({"quote", "split"}),
    "shutil": frozenset({"copy2", "copytree", "move", "rmtree", "which"}),
    "sqlite3": frozenset({"Error", "OperationalError", "connect"}),
    "stat": frozenset({"FILE_ATTRIBUTE_REPARSE_POINT", "S_IREAD", "S_IRUSR", "S_ISDIR", "S_ISLNK", "S_ISREG", "S_IWRITE", "S_IWUSR"}),
    "subprocess": frozenset({"CalledProcessError", "CREATE_NO_WINDOW", "DEVNULL", "PIPE", "Popen", "SubprocessError", "TimeoutExpired", "run"}),
    "sys": frozenset({"argv", "executable", "implementation", "path", "platform", "prefix", "stderr", "stdin", "stdout", "version_info"}),
    "tempfile": frozenset({"NamedTemporaryFile", "TemporaryDirectory", "gettempdir", "mkdtemp", "mkstemp"}),
    "threading": frozenset({"Event", "Lock", "RLock", "Thread", "local"}),
    "time": frozenset({"monotonic", "monotonic_ns", "sleep", "time"}),
    "tomllib": frozenset({"loads"}),
    "uuid": frozenset({"uuid4"}),
    "wintypes": frozenset({"BOOL", "DWORD", "HANDLE", "LPCWSTR", "LPWSTR", "WCHAR"}),
}
_ALLOWED_KERNEL32_FNS = frozenset(
    {
        "CloseHandle", "CreateToolhelp32Snapshot", "OpenProcess",
        "Process32FirstW", "Process32NextW", "QueryFullProcessImageNameW",
    }
)
_SCALAR_TYPE_NAMES = frozenset({"int", "bool", "str", "float", "bytes", "dict", "list", "tuple", "set"})
_ALLOWED_OS_PATH_ATTRS = frozenset(
    {
        "abspath", "basename", "commonpath", "dirname", "exists", "expanduser",
        "isabs", "isdir", "isfile", "isjunction", "islink", "join", "lexists",
        "normcase", "normpath", "realpath", "relpath", "samefile", "split", "splitdrive",
    }
)
_ALLOWED_CLASS_BASE_NAMES = frozenset(
    {"Exception", "RuntimeError", "ValueError", "OSError", "dict", "set", "object", "NamedTuple"}
)
_ALLOWED_FROM_MODULES = _LOCAL_STORAGE_MODULES | {m for m, _ in _ALLOWED_STDLIB_FROM_PAIRS} | {"typing"}
_ALLOWED_GETATTR_NAMES = frozenset(
    {
        "CREATE_NO_WINDOW", "ERROR_ACCESS_DENIED", "ERROR_INVALID_PARAMETER",
        "O_BINARY", "O_NOFOLLOW", "PROCESS_ALL_ACCESS", "PROCESS_QUERY_INFORMATION",
        "PROCESS_QUERY_LIMITED_INFORMATION", "base_prefix", "commands", "depths",
        "errno", "isjunction", "returncode", "st_file_attributes", "st_reparse_tag",
        "winerror",
    }
)
_BANNED_ATTR_NAMES = frozenset(
    {
        "modules", "_getframe", "_current_frames", "_current_exceptions",
        "f_builtins", "f_globals", "f_locals", "f_back", "f_code",
        "gi_frame", "gi_code", "cr_frame", "cr_code", "ag_frame", "ag_code",
        "tb_frame", "tb_next", "pythonapi", "cdll", "pydll", "oledll", "windll",
        "CDLL", "PyDLL", "OleDLL", "LoadLibrary", "_dlopen", "CFUNCTYPE",
        "WINFUNCTYPE", "PYFUNCTYPE", "get_type_hints", "_eval_type",
        "enable_load_extension", "load_extension",
    }
)
_SAFE_READ_DUNDERS = frozenset({"__init__", "__name__"})


def _stmts_always_exit(stmts: list[ast.stmt], *, in_loop: bool) -> bool:
    for stmt in stmts:
        if isinstance(stmt, (ast.Return, ast.Raise)):
            return True
        if in_loop and isinstance(stmt, (ast.Break, ast.Continue)):
            return True
        if isinstance(stmt, ast.If) and stmt.orelse:
            if _stmts_always_exit(stmt.body, in_loop=in_loop) and _stmts_always_exit(stmt.orelse, in_loop=in_loop):
                return True
    return False


def _guard_implications(expr: ast.AST, os_aliases: frozenset[str], sys_aliases: frozenset[str]) -> tuple[bool, bool]:
    """Return `(true_implies_posix, false_implies_posix)` for literal platform guard `expr`."""
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        t_pos, f_pos = _guard_implications(expr.operand, os_aliases, sys_aliases)
        return f_pos, t_pos
    if isinstance(expr, ast.BoolOp):
        parts = [_guard_implications(v, os_aliases, sys_aliases) for v in expr.values]
        if isinstance(expr.op, ast.And):
            return any(t for t, _ in parts), all(f for _, f in parts)
        if isinstance(expr.op, ast.Or):
            return all(t for t, _ in parts), any(f for _, f in parts)
        return False, False
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute):
        recv = expr.func.value
        if (
            isinstance(recv, ast.Attribute)
            and isinstance(recv.value, ast.Name)
            and recv.value.id in sys_aliases
            and recv.attr == "platform"
            and expr.func.attr == "startswith"
            and len(expr.args) == 1
            and not expr.keywords
            and isinstance(expr.args[0], ast.Constant)
            and isinstance(expr.args[0].value, str)
            and expr.args[0].value in {"win", "win32"}
        ):
            return False, True
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and len(expr.comparators) == 1:
        left, op, right = expr.left, expr.ops[0], expr.comparators[0]
        if not (
            isinstance(left, ast.Attribute)
            and isinstance(left.value, ast.Name)
            and isinstance(right, ast.Constant)
            and isinstance(right.value, str)
        ):
            return False, False
        if left.value.id in os_aliases and left.attr == "name":
            if right.value == "nt":
                if isinstance(op, ast.Eq):
                    return False, True
                if isinstance(op, ast.NotEq):
                    return True, False
            elif right.value == "posix" and isinstance(op, ast.Eq):
                return True, False
        if left.value.id in sys_aliases and left.attr == "platform" and right.value == "win32":
            if isinstance(op, ast.Eq):
                return False, True
            if isinstance(op, ast.NotEq):
                return True, False
    return False, False


def _is_exempt_direct_kill_call(call: ast.Call, imported_kill_names: frozenset[str]) -> bool:
    """Exempt only 0-arg `proc.kill()` or explicit 2-arg non-zero `int` signal literal."""
    is_bare_imported_kill = isinstance(call.func, ast.Name) and call.func.id in imported_kill_names
    if not is_bare_imported_kill and not call.args and not call.keywords:
        return True
    if (
        len(call.args) == 2
        and not call.keywords
        and not isinstance(call.args[0], ast.Starred)
        and isinstance(call.args[1], ast.Constant)
        and type(call.args[1].value) is int
        and call.args[1].value != 0
    ):
        return True
    return False


def _collect_tree_facts(
    tree: ast.Module,
) -> tuple[frozenset[str], frozenset[str], frozenset[str], list[str]]:
    """Collect `(imported_kill_names, impure_os_sys_names, pure_re_names, capability_errors)`."""
    parent_map = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    call_func_ids = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    attr_value_ids = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    getattr_obj_ids = {
        id(n.args[0])
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "getattr" and len(n.args) >= 2
    }
    imported_kills: set[str] = set()
    non_import_bound: set[str] = set()
    windll_vars: set[str] = set()
    cap_errors: list[str] = []
    scope_top_stmts: set[int] = {id(s) for s in tree.body}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            non_import_bound.add(node.name)
            scope_top_stmts.update(id(s) for s in node.body)
        elif isinstance(node, ast.ClassDef):
            non_import_bound.add(node.name)
        elif isinstance(node, ast.arg):
            non_import_bound.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            non_import_bound.add(node.id)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            non_import_bound.update(node.names)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            non_import_bound.add(node.name)
        elif isinstance(node, ast.MatchAs) and node.name:
            non_import_bound.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            non_import_bound.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            non_import_bound.add(node.rest)
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "WinDLL"
        ):
            windll_vars.add(node.targets[0].id)

    import_sources: dict[str, list[tuple[str, bool]]] = {}
    all_module_aliases: set[str] = set()
    local_module_aliases: set[str] = set()
    stdlib_alias_roots: dict[str, set[str]] = {}
    ctypes_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            in_top = id(node) in scope_top_stmts
            for alias in node.names:
                if alias.name not in _ALLOWED_EXACT_IMPORTS:
                    cap_errors.append(f"line {node.lineno} `import {alias.name}` is not in storage module allowlist")
                top_pkg = alias.name.split(".", 1)[0]
                bound = alias.asname or top_pkg
                all_module_aliases.add(bound)
                if alias.name in _LOCAL_STORAGE_MODULES:
                    local_module_aliases.add(bound)
                else:
                    mod_key = "ntpath" if alias.name == "os.path" and alias.asname else top_pkg
                    stdlib_alias_roots.setdefault(bound, set()).add(mod_key)
                if alias.name == "ctypes":
                    ctypes_aliases.add(bound)
                src = (
                    "os"
                    if (alias.name == "os" or (alias.asname is None and alias.name == "os.path"))
                    else ("sys" if alias.name == "sys" else ("re" if alias.name == "re" else "other"))
                )
                import_sources.setdefault(bound, []).append((src, in_top))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if (node.level or 0) == 0 and mod not in _ALLOWED_FROM_MODULES:
                cap_errors.append(f"line {node.lineno} `from {mod} import ...` is not in storage module allowlist")
            for alias in node.names:
                if alias.name == "*":
                    cap_errors.append(
                        f"line {node.lineno} wildcard `from {mod or '.'} import *` is banned in storage modules"
                    )
                    continue
                if mod == "typing":
                    if alias.name not in _ALLOWED_TYPING_NAMES:
                        cap_errors.append(
                            f"line {node.lineno} `from typing import {alias.name}` is banned in storage modules"
                        )
                elif (node.level or 0) == 0 and mod not in _LOCAL_STORAGE_MODULES:
                    if (mod, alias.name) not in _ALLOWED_STDLIB_FROM_PAIRS:
                        cap_errors.append(
                            f"line {node.lineno} `from {mod} import {alias.name}` is not in storage module allowlist"
                        )
                if (
                    alias.name in _REFLECTIVE_FNS
                    or alias.name in _BANNED_ATTR_NAMES
                    or (alias.name.startswith("__") and alias.name.endswith("__"))
                ):
                    cap_errors.append(
                        f"line {node.lineno} importing reflective symbol `{alias.name}` is banned in storage modules"
                    )
                bound = alias.asname or alias.name
                non_import_bound.add(bound)
                if (node.level or 0) == 0 and (mod, alias.name) in _STDLIB_SUBMODULE_IMPORTS:
                    all_module_aliases.add(bound)
                    stdlib_alias_roots.setdefault(bound, set()).add(_STDLIB_SUBMODULE_IMPORTS[(mod, alias.name)])
                if (node.level or 0) > 0 or mod in _LOCAL_STORAGE_MODULES:
                    local_module_aliases.add(bound)
                if alias.name == "kill":
                    imported_kills.add(bound)

    impure_os_sys = set(non_import_bound)
    pure_re: set[str] = set()
    for bound, entries in import_sources.items():
        srcs = {s for s, _ in entries}
        all_top = all(t for _, t in entries)
        if not all_top or len(srcs) > 1 or srcs not in ({"os"}, {"sys"}):
            impure_os_sys.add(bound)
        if bound not in non_import_bound and len(entries) == 1 and entries[0] == ("re", True):
            pure_re.add(bound)

    for node in ast.walk(tree):
        if isinstance(node, ast.MatchClass):
            cap_errors.append(f"line {node.lineno} class pattern matching is banned in storage modules")
        elif isinstance(node, ast.ClassDef):
            if node.keywords:
                cap_errors.append(f"line {node.lineno} class `{node.name}` metaclass/keywords are banned in storage modules")
            for base in node.bases:
                ok_base = (
                    isinstance(base, ast.Name)
                    and base.id in _ALLOWED_CLASS_BASE_NAMES
                    and base.id not in non_import_bound
                    and base.id not in all_module_aliases
                ) or (
                    isinstance(base, ast.Attribute)
                    and isinstance(base.value, ast.Name)
                    and base.value.id in ctypes_aliases
                    and base.value.id not in non_import_bound
                    and base.attr == "Structure"
                )
                if not ok_base:
                    cap_errors.append(
                        f"line {node.lineno} class `{node.name}` inherits disallowed or shadowed base in storage modules"
                    )
        elif isinstance(node, ast.Attribute):
            is_dunder = node.attr.startswith("__") and node.attr.endswith("__")
            is_private = node.attr.startswith("_") and not is_dunder
            if node.attr in _BANNED_ATTR_NAMES:
                cap_errors.append(f"line {node.lineno} `.{node.attr}` access is banned in storage modules")
            elif is_private and not (
                isinstance(node.value, ast.Name) and (node.value.id == "self" or node.value.id in local_module_aliases)
            ):
                cap_errors.append(
                    f"line {node.lineno} private attribute `.{node.attr}` access on external object is banned in storage modules"
                )
            elif isinstance(node.ctx, (ast.Store, ast.Del)) and (
                node.attr in {"name", "platform", "kill", "compile"}
                or is_dunder
                or (isinstance(node.value, ast.Name) and node.value.id in (all_module_aliases | windll_vars))
            ):
                cap_errors.append(
                    f"line {node.lineno} mutating or deleting `.{node.attr}` is banned in storage modules"
                )
            elif is_dunder and (
                node.attr not in _SAFE_READ_DUNDERS
                or (
                    node.attr == "__init__"
                    and not (
                        id(node) in call_func_ids
                        and isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == "super"
                        and "super" not in non_import_bound
                    )
                )
            ):
                cap_errors.append(
                    f"line {node.lineno} reflective dunder `.{node.attr}` access is banned in storage modules"
                )
            elif isinstance(node.value, ast.Name) and node.value.id in windll_vars:
                if node.attr not in _ALLOWED_KERNEL32_FNS:
                    cap_errors.append(
                        f"line {node.lineno} `{node.value.id}.{node.attr}` is outside allowlisted kernel32 APIs"
                    )
            elif isinstance(node.value, ast.Name) and node.value.id in stdlib_alias_roots:
                roots = stdlib_alias_roots[node.value.id]
                if len(roots) != 1 or node.attr not in _ALLOWED_STDLIB_MOD_ATTRS.get(next(iter(roots)), frozenset()):
                    cap_errors.append(
                        f"line {node.lineno} `{node.value.id}.{node.attr}` is outside allowlisted stdlib storage APIs"
                    )
                if node.attr == "path" and "os" in roots and id(node) not in attr_value_ids and id(node) not in getattr_obj_ids:
                    cap_errors.append(
                        f"line {node.lineno} first-class `os.path` module reference is banned in storage modules"
                    )
            elif (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and "os" in stdlib_alias_roots.get(node.value.value.id, ())
                and node.value.attr == "path"
                and node.attr not in _ALLOWED_OS_PATH_ATTRS
            ):
                cap_errors.append(
                    f"line {node.lineno} `os.path.{node.attr}` is outside allowlisted path APIs"
                )
            if isinstance(node.ctx, ast.Load) and node.attr in {"kill", "WinDLL"} and id(node) not in call_func_ids:
                cap_errors.append(
                    f"line {node.lineno} first-class/aliased `.{node.attr}` reference is banned in storage modules"
                )
            elif isinstance(node.ctx, ast.Load) and node.attr in _REFLECTIVE_FNS and id(node) not in call_func_ids:
                cap_errors.append(
                    f"line {node.lineno} first-class/aliased `.{node.attr}` reference is banned in storage modules"
                )
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id == "__builtins__":
                cap_errors.append(f"line {node.lineno} `__builtins__` access is banned in storage modules")
            elif node.id == "type" and id(node) not in call_func_ids:
                cap_errors.append(f"line {node.lineno} first-class `type` reference is banned in storage modules")
            elif node.id in (ctypes_aliases | windll_vars) and id(node) not in attr_value_ids:
                cap_errors.append(
                    f"line {node.lineno} first-class `ctypes`/`WinDLL` reference `{node.id}` is banned in storage modules"
                )
            elif node.id in all_module_aliases and id(node) not in attr_value_ids and id(node) not in getattr_obj_ids:
                cap_errors.append(
                    f"line {node.lineno} first-class module alias `{node.id}` reference is banned in storage modules"
                )
            elif node.id in imported_kills and id(node) not in call_func_ids:
                cap_errors.append(
                    f"line {node.lineno} first-class/aliased `{node.id}` reference is banned in storage modules"
                )
            elif node.id in _REFLECTIVE_FNS and id(node) not in call_func_ids:
                cap_errors.append(
                    f"line {node.lineno} first-class/aliased `{node.id}` reference is banned in storage modules"
                )
        elif isinstance(node, ast.Call):
            fn = node.func
            if not isinstance(fn, (ast.Name, ast.Attribute)):
                cap_errors.append(
                    f"line {node.lineno} indirect/chained callee expression is banned in storage modules"
                )
                continue
            is_bare_name = isinstance(fn, ast.Name)
            fn_name = fn.id if is_bare_name else fn.attr
            if is_bare_name and fn_name == "type":
                par = parent_map.get(node)
                ok_type_use = (
                    "type" not in non_import_bound
                    and len(node.args) == 1
                    and not isinstance(node.args[0], ast.Starred)
                    and not node.keywords
                    and (
                        (isinstance(par, ast.Attribute) and par.value is node and par.attr == "__name__")
                        or (
                            isinstance(par, ast.Compare)
                            and len(par.ops) == 1
                            and len(par.comparators) == 1
                            and isinstance(par.ops[0], (ast.Is, ast.IsNot))
                            and (
                                (par.left is node and isinstance(par.comparators[0], ast.Name) and par.comparators[0].id in _SCALAR_TYPE_NAMES and par.comparators[0].id not in non_import_bound)
                                or (par.comparators[0] is node and isinstance(par.left, ast.Name) and par.left.id in _SCALAR_TYPE_NAMES and par.left.id not in non_import_bound)
                            )
                        )
                    )
                )
                if not ok_type_use:
                    cap_errors.append(
                        f"line {node.lineno} first-class or dynamic `type(...)` is banned in storage modules"
                    )
            elif fn_name in (_REFLECTIVE_FNS - {"getattr", "compile"}):
                cap_errors.append(f"line {node.lineno} `{fn_name}(...)` is banned in storage modules")
            elif fn_name == "WinDLL":
                par = parent_map.get(node)
                ok_windll = (
                    isinstance(fn, ast.Attribute)
                    and isinstance(fn.value, ast.Name)
                    and fn.value.id in ctypes_aliases
                    and fn.value.id not in non_import_bound
                    and len(node.args) == 1
                    and not isinstance(node.args[0], ast.Starred)
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                    and node.args[0].value.lower() in {"kernel32", "kernel32.dll"}
                    and all(
                        kw.arg == "use_last_error" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, bool)
                        for kw in node.keywords
                    )
                    and (
                        (isinstance(par, ast.Assign) and len(par.targets) == 1 and isinstance(par.targets[0], ast.Name) and par.value is node)
                        or (isinstance(par, ast.Attribute) and par.value is node and par.attr in _ALLOWED_KERNEL32_FNS)
                    )
                )
                if not ok_windll:
                    cap_errors.append(f"line {node.lineno} non-kernel32 or unbound `WinDLL(...)` is banned in storage modules")
            elif fn_name == "getattr":
                if (
                    not is_bare_name
                    or "getattr" in non_import_bound
                    or len(node.args) < 2
                    or len(node.args) > 3
                    or node.keywords
                    or not isinstance(node.args[1], ast.Constant)
                    or not isinstance(node.args[1].value, str)
                    or node.args[1].value not in _ALLOWED_GETATTR_NAMES
                ):
                    cap_errors.append(
                        f"line {node.lineno} `getattr(...)` outside allowlisted OS/stat attributes is banned in storage modules"
                    )

    return frozenset(imported_kills), frozenset(impure_os_sys), frozenset(pure_re), cap_errors


def inspect_storage_module_windows_pid_safety(path: Path) -> list[str]:
    """Verify storage module `path` never calls `os.kill(pid, 0)` outside proven POSIX branches."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imported_kills, impure, pure_re_global, errors = _collect_tree_facts(tree)

    def _visit_expr(
        node: ast.AST,
        posix_proven: bool,
        scope_name: str,
        m_os: frozenset[str],
        m_sys: frozenset[str],
        m_re: frozenset[str],
    ) -> None:
        if isinstance(node, ast.Lambda):
            for dflt in (*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)):
                _visit_expr(dflt, posix_proven, scope_name, m_os, m_sys, m_re)
            _visit_expr(node.body, posix_proven, scope_name, m_os, m_sys, m_re)
            return
        if isinstance(node, _COMPREHENSION_TYPES):
            for gen in node.generators:
                _visit_expr(gen.iter, posix_proven, scope_name, m_os, m_sys, m_re)
                _visit_expr(gen.target, posix_proven, scope_name, m_os, m_sys, m_re)
                for cond in gen.ifs:
                    _visit_expr(cond, posix_proven, scope_name, m_os, m_sys, m_re)
                    t_pos, _ = _guard_implications(cond, m_os, m_sys)
                    posix_proven = posix_proven or t_pos
            if isinstance(node, ast.DictComp):
                _visit_expr(node.key, posix_proven, scope_name, m_os, m_sys, m_re)
                _visit_expr(node.value, posix_proven, scope_name, m_os, m_sys, m_re)
            else:
                _visit_expr(node.elt, posix_proven, scope_name, m_os, m_sys, m_re)
            return
        if isinstance(node, ast.IfExp):
            _visit_expr(node.test, posix_proven, scope_name, m_os, m_sys, m_re)
            t_pos, f_pos = _guard_implications(node.test, m_os, m_sys)
            _visit_expr(node.body, posix_proven or t_pos, scope_name, m_os, m_sys, m_re)
            _visit_expr(node.orelse, posix_proven or f_pos, scope_name, m_os, m_sys, m_re)
            return
        if isinstance(node, ast.Call):
            fn = node.func
            if (isinstance(fn, ast.Name) and fn.id == "compile") or (
                isinstance(fn, ast.Attribute) and fn.attr == "compile"
            ):
                if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in m_re):
                    errors.append(f"line {node.lineno} non-regex `compile(...)` is banned in storage modules")
            is_kill_call = (isinstance(fn, ast.Attribute) and fn.attr == "kill") or (
                isinstance(fn, ast.Name) and fn.id in imported_kills
            )
            if is_kill_call and not _is_exempt_direct_kill_call(node, imported_kills) and not posix_proven:
                errors.append(
                    f"line {node.lineno} `{scope_name}` calls unguarded `os.kill(pid, 0)` "
                    "(terminates or misprobes processes on Windows; guard with `os.name != 'nt'` or use Win32 `OpenProcess`)"
                )
        for child in ast.iter_child_nodes(node):
            _visit_expr(child, posix_proven, scope_name, m_os, m_sys, m_re)

    def _walk_block(
        block: list[ast.stmt],
        blk_posix: bool,
        scope_name: str,
        m_os: frozenset[str],
        m_sys: frozenset[str],
        m_re: frozenset[str],
        *,
        top_block: bool,
        in_loop: bool = False,
        is_class_body: bool = False,
        lex_os: frozenset[str] = frozenset(),
        lex_sys: frozenset[str] = frozenset(),
        lex_re: frozenset[str] = frozenset(),
    ) -> None:
        cur_pos = blk_posix
        cur_o, cur_s, cur_r = set(m_os), set(m_sys), set(m_re)
        for stmt in block:
            fo, fs, fr = frozenset(cur_o), frozenset(cur_s), frozenset(cur_r)
            child_o = lex_os if is_class_body else fo
            child_s = lex_sys if is_class_body else fs
            child_r = lex_re if is_class_body else fr
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in stmt.decorator_list:
                    _visit_expr(dec, cur_pos, scope_name, fo, fs, fr)
                for tp in getattr(stmt, "type_params", ()):
                    _visit_expr(tp, cur_pos, scope_name, fo, fs, fr)
                for arg in (*stmt.args.posonlyargs, *stmt.args.args, *stmt.args.kwonlyargs, stmt.args.vararg, stmt.args.kwarg):
                    if arg is not None and arg.annotation is not None:
                        _visit_expr(arg.annotation, cur_pos, scope_name, fo, fs, fr)
                if stmt.returns is not None:
                    _visit_expr(stmt.returns, cur_pos, scope_name, fo, fs, fr)
                for dflt in (*stmt.args.defaults, *(d for d in stmt.args.kw_defaults if d is not None)):
                    _visit_expr(dflt, cur_pos, scope_name, fo, fs, fr)
                _walk_block(stmt.body, cur_pos, stmt.name, child_o, child_s, child_r, top_block=True, in_loop=False)
            elif isinstance(stmt, ast.ClassDef):
                for dec in stmt.decorator_list:
                    _visit_expr(dec, cur_pos, scope_name, fo, fs, fr)
                for tp in getattr(stmt, "type_params", ()):
                    _visit_expr(tp, cur_pos, scope_name, fo, fs, fr)
                for b in stmt.bases:
                    _visit_expr(b, cur_pos, scope_name, fo, fs, fr)
                for kw in stmt.keywords:
                    _visit_expr(kw.value, cur_pos, scope_name, fo, fs, fr)
                _walk_block(
                    stmt.body, cur_pos, stmt.name, child_o, child_s, child_r,
                    top_block=False, in_loop=False, is_class_body=True,
                    lex_os=child_o, lex_sys=child_s, lex_re=child_r,
                )
            elif isinstance(stmt, ast.If):
                _visit_expr(stmt.test, cur_pos, scope_name, fo, fs, fr)
                t_pos, f_pos = _guard_implications(stmt.test, fo, fs)
                _walk_block(stmt.body, cur_pos or t_pos, scope_name, fo, fs, fr, top_block=False, in_loop=in_loop)
                _walk_block(stmt.orelse, cur_pos or f_pos, scope_name, fo, fs, fr, top_block=False, in_loop=in_loop)
                if not stmt.orelse and f_pos and _stmts_always_exit(stmt.body, in_loop=in_loop):
                    cur_pos = True
            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                _visit_expr(stmt.iter, cur_pos, scope_name, fo, fs, fr)
                _visit_expr(stmt.target, cur_pos, scope_name, fo, fs, fr)
                _walk_block(stmt.body, cur_pos, scope_name, fo, fs, fr, top_block=False, in_loop=True)
                _walk_block(stmt.orelse, cur_pos, scope_name, fo, fs, fr, top_block=False, in_loop=in_loop)
            elif isinstance(stmt, ast.While):
                _visit_expr(stmt.test, cur_pos, scope_name, fo, fs, fr)
                t_pos, _ = _guard_implications(stmt.test, fo, fs)
                _walk_block(stmt.body, cur_pos or t_pos, scope_name, fo, fs, fr, top_block=False, in_loop=True)
                _walk_block(stmt.orelse, cur_pos, scope_name, fo, fs, fr, top_block=False, in_loop=in_loop)
            elif isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                _walk_block(stmt.body, cur_pos, scope_name, fo, fs, fr, top_block=False, in_loop=False)
                _walk_block(stmt.orelse, cur_pos, scope_name, fo, fs, fr, top_block=False, in_loop=in_loop)
                for h in stmt.handlers:
                    if h.type is not None:
                        _visit_expr(h.type, cur_pos, scope_name, fo, fs, fr)
                    _walk_block(h.body, cur_pos, scope_name, fo, fs, fr, top_block=False, in_loop=in_loop)
                _walk_block(stmt.finalbody, cur_pos, scope_name, fo, fs, fr, top_block=False, in_loop=in_loop)
            elif isinstance(stmt, ast.Match):
                _visit_expr(stmt.subject, cur_pos, scope_name, fo, fs, fr)
                for mc in stmt.cases:
                    c_pos = cur_pos
                    if mc.guard is not None:
                        _visit_expr(mc.guard, cur_pos, scope_name, fo, fs, fr)
                        t_pos, _ = _guard_implications(mc.guard, fo, fs)
                        c_pos = c_pos or t_pos
                    _walk_block(mc.body, c_pos, scope_name, fo, fs, fr, top_block=False, in_loop=in_loop)
            else:
                for _, val in ast.iter_fields(stmt):
                    if isinstance(val, list):
                        if val and all(isinstance(it, ast.stmt) for it in val):
                            _walk_block(val, cur_pos, scope_name, fo, fs, fr, top_block=False, in_loop=in_loop)
                        else:
                            for it in val:
                                if isinstance(it, ast.AST):
                                    _visit_expr(it, cur_pos, scope_name, fo, fs, fr)
                    elif isinstance(val, ast.AST):
                        _visit_expr(val, cur_pos, scope_name, fo, fs, fr)

            if top_block and isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    if alias.name == "re" and bound in pure_re_global:
                        cur_r.add(bound)
                    if bound in impure:
                        continue
                    if alias.name == "os" or (alias.asname is None and alias.name == "os.path"):
                        cur_o.add(bound)
                    elif alias.name == "sys":
                        cur_s.add(bound)

    _walk_block(tree.body, False, "<module>", frozenset(), frozenset(), frozenset(), top_block=True)
    return errors
