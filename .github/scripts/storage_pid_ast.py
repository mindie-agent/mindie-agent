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
_REFLECTIVE_FNS = frozenset({"getattr", "setattr", "delattr", "eval", "exec", "compile", "vars", "globals", "locals", "attrgetter", "methodcaller", "__import__", "breakpoint"})
_ALLOWED_LOCAL_FROM_MAP: dict[tuple[int, str], frozenset[str]] = {
    (0, "bounded_process"): frozenset({"run"}),
    (0, "genstate"): frozenset({"launch_dir", "read_current", "read_json", "receipts_dir", "update_dir"}),
    (0, "host_pin_refresh"): frozenset({"scheduled_pins"}),
    (0, "mindie_knowledge"): frozenset({"storage"}),
    (0, "mindie_knowledge.filesystem"): frozenset({"is_junction", "path_aliases", "path_identity"}),
    (0, "mindie_knowledge.state_layout"): frozenset({"DATABASE", "state_root"}),
    (0, "mindie_knowledge.storage"): frozenset({"acquire_runtime_lease", "collect_global_protected_roots", "configure_same_volume_uv_cache", "is_lease_held", "is_path_used_by_live_process", "legacy_roots", "live_process_prefixes", "owning_dir", "prune_component_runtimes", "retire_directory", "sweep_legacy_installations", "sweep_trash"}),
    (0, "mindie_knowledge.storage.legacy_roots"): frozenset({"_config_homes", "protected_source_roots"}),
    (0, "mindie_knowledge.storage.lifecycle"): frozenset({"has_git_ancestor", "is_junction", "is_protected_path", "is_within_roots"}),
    (0, "paths"): frozenset({"atomic_write_json", "config_path", "data_home", "load_adapter_config", "read_json", "state_dir", "workbuddy_config_dir"}),
    (0, "product_contract"): frozenset({"installed_version"}),
    (0, "remote_state_guard"): frozenset({"MAX_ENDPOINT_ROOTS", "MAX_SESSION_ROOTS", "guarded_endpoint_retention", "guarded_session_retention", "has_unresolved_state", "unresolved_state"}),
    (0, "storage_common"): frozenset({"MAINTENANCE_INTERVAL_SECONDS", "MARKER_NAME", "MAX_JSON_BYTES", "MAX_SESSION_ENTRIES", "MAX_WALK_FILES", "MAX_WARNINGS", "PENDING_BIND_STATUSES", "RELEASE_BUDGET_SECONDS", "RESOLVED_SUBMISSION_STATES", "SCHEMA", "SESSION_BUDGET_SECONDS", "SESSION_RETENTION_SECONDS", "SWEEP_BUDGET_SECONDS", "TERMINAL_BIND_STATUSES", "_TRASH_PREFIX", "_VERSION", "_binding", "_bounded_deadline", "_expired", "_identity", "_json_safe", "_read_json", "_recent_marker", "_remaining", "_roots", "_state_dir", "_warn", "_write_json_atomic", "attach_cleanup", "cleanup_fields"}),
    (0, "storage_pid_ast"): frozenset({"inspect_helper_windows_pid_safety", "inspect_storage_module_windows_pid_safety"}),
    (0, "storage_reclaim"): frozenset({"prune_sessions", "sweep_installations"}),
    (0, "storage_releases"): frozenset({"active_version", "prune_release_entries", "refresh_release_entry", "render_entry"}),
    (0, "storage_spool"): frozenset({"SPOOL_BUDGET_SECONDS", "SPOOL_BUNDLE_MIN_AGE_SECONDS", "SPOOL_MAX_AGE_SECONDS", "SPOOL_SESSION_LIMIT", "_held_spool_lock", "lock_inode_matches", "prune_spool_transcripts", "spool_maintenance_due", "write_spool_maintenance_marker"}),
    (0, "storage_support"): frozenset({"account", "budget", "expired", "is_absolute", "merge", "normalize_windows_path", "note", "path_key", "path_text", "unlink_file"}),
    (0, "storage_temp_ast"): frozenset({"inspect_python_temp_hygiene", "iter_direct_nodes", "non_import_bound_names"}),
    (1, "leases"): frozenset({"BUILDER_LOCK_NAMES", "RuntimeLease", "acquire_retirement_locks", "acquire_runtime_lease", "is_lease_held", "is_path_used_by_live_process", "live_process_prefixes", "windows_lease_present"}),
    (1, "legacy"): frozenset({"collect_global_protected_roots", "owning_dir", "sweep_legacy_installations"}),
    (1, "legacy_roots"): frozenset({"MARKER_SCHEMA", "_check", "_config_documents", "_config_homes", "_data_homes", "_discover_targets", "_entries", "_env", "_home", "_read_json", "_strings", "collect_global_protected_roots", "owning_dir", "protected_source_roots"}),
    (1, "lifecycle"): frozenset({"_builder_locked", "_expired", "configure_same_volume_uv_cache", "fs_path", "has_git_ancestor", "is_junction", "is_own_runtime_path", "is_protected_path", "is_within_roots", "prune_component_runtimes", "retire_directory", "same_volume_cache_dir", "sweep_trash"}),
    (1, "uv_cache"): frozenset({"UV_CACHE_DIRECTORY", "_device", "configure_same_volume_uv_cache", "same_volume_cache_dir"}),
    (2, "_host_exec"): frozenset({"which_native"}),
    (2, "filesystem"): frozenset({"filesystem_path", "is_junction", "path_identity"}),
    (2, "loop.locks"): frozenset({"lock_file", "lock_held", "unlock_file"}),
}
_LOCAL_STORAGE_MODULES = frozenset({m for lvl, m in _ALLOWED_LOCAL_FROM_MAP if lvl == 0} | {"mindie_paths", "storage", "storage_gc", "storage_leases", "storage_lifecycle"})
_ALLOWED_EXACT_IMPORTS = {"_winapi", "argparse", "ast", "contextlib", "ctypes", "errno", "fcntl", "hashlib", "json", "mindie_paths", "msvcrt", "ntpath", "os", "os.path", "pathlib", "plistlib", "re", "select", "shlex", "shutil", "sqlite3", "stat", "storage_support", "subprocess", "sys", "tempfile", "threading", "time", "tomllib", "uuid"}
_ALLOWED_STDLIB_FROM_PAIRS = frozenset({("__future__", "annotations"), ("collections.abc", "Iterator"), ("contextlib", "ExitStack"), ("contextlib", "contextmanager"), ("contextlib", "suppress"), ("ctypes", "wintypes"), ("os", "kill"), ("pathlib", "Path"), ("urllib.parse", "quote"), ("xml.etree", "ElementTree")})
_STDLIB_SUBMODULE_IMPORTS: dict[tuple[str, str], str] = {("ctypes", "wintypes"): "wintypes", ("xml.etree", "ElementTree"): "ElementTree", ("mindie_knowledge", "storage"): "storage", ("mindie_knowledge.storage", "legacy_roots"): "legacy_roots"}
_ALLOWED_TYPING_NAMES = frozenset({"Any", "Callable", "ClassVar", "Dict", "Final", "FrozenSet", "Generator", "IO", "Iterable", "Iterator", "List", "Literal", "Mapping", "MutableMapping", "NamedTuple", "NoReturn", "Optional", "Protocol", "Sequence", "Set", "TextIO", "Tuple", "TYPE_CHECKING", "TypeAlias", "TypedDict", "Union", "cast", "overload"})
_ALLOWED_STDLIB_MOD_ATTRS: dict[str, frozenset[str]] = {
    "_winapi": frozenset({"CloseHandle", "GetExitCodeProcess", "OpenProcess", "STILL_ACTIVE"}),
    "ElementTree": frozenset({"ParseError", "fromstring"}),
    "argparse": frozenset({"ArgumentParser"}),
    "ast": frozenset({"Constant", "parse", "walk"}),
    "contextlib": frozenset({"ExitStack", "contextmanager", "suppress"}),
    "ctypes": frozenset({"POINTER", "Structure", "WinDLL", "byref", "c_bool", "c_int", "c_long", "c_size_t", "c_uint32", "c_uint64", "c_ulong", "c_void_p", "c_wchar", "c_wchar_p", "create_unicode_buffer", "get_last_error", "sizeof"}),
    "errno": frozenset({"EACCES", "EDEADLK", "EEXIST", "EINVAL", "ENOENT", "EPERM", "ESRCH"}),
    "fcntl": frozenset({"LOCK_EX", "LOCK_NB", "LOCK_SH", "LOCK_UN", "flock"}),
    "hashlib": frozenset({"sha256"}),
    "json": frozenset({"JSONDecodeError", "dump", "dumps", "load", "loads"}),
    "legacy_roots": frozenset({"_config_homes"}),
    "mindie_paths": frozenset({"config_file", "config_home", "data_home"}),
    "msvcrt": frozenset({"LK_LOCK", "LK_NBLCK", "LK_UNLCK", "locking"}),
    "ntpath": frozenset({"abspath", "normcase", "normpath"}),
    "os": frozenset({"O_APPEND", "O_CREAT", "O_EXCL", "O_RDONLY", "O_RDWR", "O_WRONLY", "PathLike", "SEEK_SET", "W_OK", "X_OK", "access", "chmod", "close", "environ", "fdopen", "fsdecode", "fsencode", "fspath", "fstat", "fsync", "getpid", "kill", "listdir", "lseek", "lstat", "makedirs", "mkdir", "name", "open", "path", "pathsep", "read", "readlink", "remove", "rename", "replace", "rmdir", "scandir", "sep", "stat", "unlink", "utime", "walk", "write"}),
    "pathlib": frozenset({"Path", "PurePath", "PosixPath", "WindowsPath"}),
    "plistlib": frozenset({"loads"}),
    "re": frozenset({"IGNORECASE", "compile", "escape", "findall", "fullmatch", "match", "search", "split", "sub"}),
    "select": frozenset({"select"}),
    "shlex": frozenset({"quote", "split"}),
    "shutil": frozenset({"copy2", "copytree", "move", "rmtree", "which"}),
    "sqlite3": frozenset({"Error", "OperationalError", "connect"}),
    "stat": frozenset({"FILE_ATTRIBUTE_REPARSE_POINT", "S_IREAD", "S_IRUSR", "S_ISDIR", "S_ISLNK", "S_ISREG", "S_IWRITE", "S_IWUSR"}),
    "storage": frozenset({"acquire_runtime_lease", "is_path_used_by_live_process", "live_process_prefixes", "owning_dir", "prune_component_runtimes", "retire_directory", "sweep_legacy_installations"}),
    "storage_support": frozenset({"MAX_CONFIG_DOCUMENTS", "config_documents", "config_homes", "config_pins", "default_config_homes", "forbidden_roots", "has_git_ancestor", "is_absolute", "link_free", "path_key", "path_text", "referenced_json_paths"}),
    "subprocess": frozenset({"CalledProcessError", "CREATE_NO_WINDOW", "DEVNULL", "PIPE", "Popen", "SubprocessError", "TimeoutExpired"}),
    "sys": frozenset({"argv", "executable", "implementation", "path", "platform", "prefix", "stderr", "stdin", "stdout", "version_info"}),
    "tempfile": frozenset({"NamedTemporaryFile", "TemporaryDirectory", "gettempdir", "mkdtemp", "mkstemp"}),
    "threading": frozenset({"Event", "Lock", "RLock", "Thread", "local"}),
    "time": frozenset({"monotonic", "monotonic_ns", "sleep", "time"}),
    "tomllib": frozenset({"loads"}),
    "uuid": frozenset({"uuid4"}),
    "wintypes": frozenset({"BOOL", "DWORD", "HANDLE", "LPCWSTR", "LPWSTR", "WCHAR"}),
}
_ALLOWED_KERNEL32_FNS = frozenset({"CloseHandle", "CreateToolhelp32Snapshot", "OpenProcess", "Process32FirstW", "Process32NextW", "QueryFullProcessImageNameW"})
_SCALAR_TYPE_NAMES = frozenset({"int", "bool", "str", "float", "bytes", "dict", "list", "tuple", "set"})
_ALLOWED_OS_PATH_ATTRS = frozenset({"abspath", "basename", "commonpath", "dirname", "exists", "expanduser", "isabs", "isdir", "isfile", "isjunction", "islink", "join", "lexists", "normcase", "normpath", "realpath", "relpath", "samefile", "split", "splitdrive"})
_ALLOWED_CLASS_BASE_NAMES = frozenset({"Exception", "RuntimeError", "ValueError", "OSError", "dict", "set", "object", "NamedTuple"})
_ALLOWED_FROM_MODULES = _LOCAL_STORAGE_MODULES | {m for m, _ in _ALLOWED_STDLIB_FROM_PAIRS} | {"typing"}
_ALLOWED_GETATTR_NAMES = frozenset({"CREATE_NO_WINDOW", "ERROR_ACCESS_DENIED", "ERROR_INVALID_PARAMETER", "O_BINARY", "O_NOFOLLOW", "PROCESS_ALL_ACCESS", "PROCESS_QUERY_INFORMATION", "PROCESS_QUERY_LIMITED_INFORMATION", "base_prefix", "commands", "depths", "errno", "isjunction", "returncode", "st_file_attributes", "st_reparse_tag", "winerror"})
_BANNED_ATTR_NAMES = frozenset({"modules", "_getframe", "_current_frames", "_current_exceptions", "f_builtins", "f_globals", "f_locals", "f_back", "f_code", "gi_frame", "gi_code", "cr_frame", "cr_code", "ag_frame", "ag_code", "tb_frame", "tb_next", "pythonapi", "cdll", "pydll", "oledll", "windll", "CDLL", "PyDLL", "OleDLL", "LoadLibrary", "_dlopen", "CFUNCTYPE", "WINFUNCTYPE", "PYFUNCTYPE", "get_type_hints", "_eval_type", "enable_load_extension", "load_extension", "leases", "lifecycle", "legacy", "subprocess", "ctypes", "_winapi", "ntpath", "shutil", "sys", "os", "re", "tempfile", "msvcrt", "fcntl", "sqlite3"})
_SAFE_READ_DUNDERS = frozenset({"__init__", "__name__"})
_ALLOWED_SELF_PRIVATE_ATTRS = frozenset({"_descriptor", "_descriptors", "_lease_file"})
_ALLOWED_LOCAL_PRIVATE_ATTRS = frozenset({"_config_homes"})
_ALLOWED_HELPER_IMPORTS = _ALLOWED_EXACT_IMPORTS | {"admission", "atexit", "bounded", "codecs", "consent", "diagnostic_support", "entry", "entry_arguments", "entry_state", "genstate", "heapq", "http.client", "identity", "knowledge_service", "math", "paths", "pywintypes", "selectors", "sharing", "signal", "socket", "ssl", "struct", "updater_schedule", "urllib.error", "win32file", "windows_process", "xml.etree.ElementTree", "yaml"}
_ALLOWED_HELPER_STDLIB_FROM_PAIRS = _ALLOWED_STDLIB_FROM_PAIRS - {("os", "kill")} | {("contextvars", "ContextVar"), ("dataclasses", "dataclass"), ("dataclasses", "field"), ("datetime", "datetime"), ("datetime", "timedelta"), ("functools", "cache"), ("importlib", "import_module"), ("importlib", "metadata"), ("importlib.metadata", "PackageNotFoundError"), ("importlib.metadata", "version"), ("urllib.parse", "unquote"), ("urllib.parse", "urlparse")}
_ALLOWED_HELPER_LOCAL_FROM_PREFIXES = frozenset({"admission", "bounded", "consent", "diagnostic_support", "entry", "entry_arguments", "entry_state", "genstate", "identity", "knowledge_service", "mindie_diagnostics", "mindie_knowledge", "paths", "process_helpers", "remote_dev", "sharing", "storage_lifecycle", "updater_schedule"})
_ALLOWED_HELPER_OS_ATTRS = _ALLOWED_STDLIB_MOD_ATTRS["os"] | {"O_BINARY", "O_NOFOLLOW", "O_NONBLOCK", "O_TRUNC", "defpath", "devnull", "ftruncate", "getcwd", "getpgid", "getpgrp", "getuid", "pipe", "strerror", "uname"}


def _stmts_always_exit(stmts: list[ast.stmt], *, in_loop: bool) -> bool:
    for stmt in stmts:
        if isinstance(stmt, (ast.Return, ast.Raise)) or (in_loop and isinstance(stmt, (ast.Break, ast.Continue))):
            return True
        if isinstance(stmt, ast.If) and stmt.orelse and _stmts_always_exit(stmt.body, in_loop=in_loop) and _stmts_always_exit(stmt.orelse, in_loop=in_loop):
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
        return (all(t for t, _ in parts), any(f for _, f in parts)) if isinstance(expr.op, ast.Or) else (False, False)
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute):
        recv = expr.func.value
        if (
            isinstance(recv, ast.Attribute) and isinstance(recv.value, ast.Name) and recv.value.id in sys_aliases
            and recv.attr == "platform" and expr.func.attr == "startswith" and len(expr.args) == 1 and not expr.keywords
            and isinstance(expr.args[0], ast.Constant) and isinstance(expr.args[0].value, str) and expr.args[0].value in {"win", "win32"}
        ):
            return False, True
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and len(expr.comparators) == 1:
        left, op, right = expr.left, expr.ops[0], expr.comparators[0]
        if not (isinstance(left, ast.Attribute) and isinstance(left.value, ast.Name) and isinstance(right, ast.Constant) and isinstance(right.value, str)):
            return False, False
        if left.value.id in os_aliases and left.attr == "name":
            if right.value == "nt":
                return (False, True) if isinstance(op, ast.Eq) else ((True, False) if isinstance(op, ast.NotEq) else (False, False))
            if right.value == "posix" and isinstance(op, ast.Eq):
                return True, False
        if left.value.id in sys_aliases and left.attr == "platform" and right.value == "win32":
            return (False, True) if isinstance(op, ast.Eq) else ((True, False) if isinstance(op, ast.NotEq) else (False, False))
    return False, False


def _is_exempt_direct_kill_call(call: ast.Call, imported_kill_names: frozenset[str]) -> bool:
    """Exempt only 0-arg `proc.kill()` or explicit 2-arg non-zero `int` signal literal."""
    is_imp = (isinstance(call.func, ast.Name) and call.func.id in imported_kill_names) or (isinstance(call.func, ast.Attribute) and call.func.attr in imported_kill_names)
    if not is_imp and not call.args and not call.keywords:
        return True
    return len(call.args) == 2 and not call.keywords and not isinstance(call.args[0], ast.Starred) and isinstance(call.args[1], ast.Constant) and type(call.args[1].value) is int and call.args[1].value != 0


def _is_long_flag(expr: ast.AST, opt_vars: set[str]) -> bool:
    return (isinstance(expr, ast.Constant) and isinstance(expr.value, str) and expr.value.startswith("--")) or (isinstance(expr, ast.Name) and expr.id in opt_vars)


def _is_str_call(expr: ast.AST) -> bool:
    return isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == "str" and len(expr.args) == 1 and not expr.keywords


def _count_scope_bindings(root: ast.AST) -> dict[str, int]:
    counts: dict[str, int] = {}
    def _inc(name: str | None) -> None:
        if name:
            counts[name] = counts.get(name, 0) + 1
    for sub in ast.walk(root):
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
            _inc(sub.name)
        elif isinstance(sub, ast.arg):
            _inc(sub.arg)
        elif isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            _inc(sub.id)
        elif isinstance(sub, (ast.Global, ast.Nonlocal)):
            for nm in sub.names:
                _inc(nm)
        elif isinstance(sub, ast.MatchMapping):
            _inc(sub.rest)
        elif isinstance(sub, ast.Import):
            for al in sub.names:
                _inc(al.asname or al.name.split(".", 1)[0])
        elif isinstance(sub, ast.ImportFrom):
            for al in sub.names:
                _inc(al.asname or al.name)
    return counts


def _is_self_dispatch_bounded_run(
    call: ast.Call, fn_scope: ast.AST | None, all_bindings: dict[str, int], pure_paths: set[str]
) -> bool:
    if not isinstance(fn_scope, ast.FunctionDef) or len(call.args) < 2:
        return False
    if not (isinstance(call.args[0], ast.Name) and isinstance(call.args[1], ast.Constant) and call.args[1].value == ""):
        return False
    if any(kw.arg not in {"timeout", "env", "max_output"} for kw in call.keywords):
        return False
    if "__file__" in all_bindings or "str" in all_bindings or "Path" not in pure_paths:
        return False
    argv_var, bcounts = call.args[0].id, _count_scope_bindings(fn_scope)
    pmap = {child: parent for parent in ast.walk(fn_scope) for child in ast.iter_child_nodes(parent)}
    assigns: dict[str, list[ast.Assign]] = {}
    opt_vars: set[str] = set()
    for sub in ast.walk(fn_scope):
        if sub is not fn_scope and isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return False
        if isinstance(sub, ast.Constant) and sub.value in {"-c", "-m"}:
            return False
        if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name):
            assigns.setdefault(sub.targets[0].id, []).append(sub)
        elif isinstance(sub, ast.For) and isinstance(sub.target, ast.Tuple) and len(sub.target.elts) == 2 and isinstance(sub.target.elts[0], ast.Name):
            if isinstance(sub.iter, ast.Tuple) and sub.iter.elts and all(
                isinstance(p, ast.Tuple) and len(p.elts) == 2 and isinstance(p.elts[0], ast.Constant) and isinstance(p.elts[0].value, str) and p.elts[0].value.startswith("--")
                for p in sub.iter.elts
            ) and bcounts.get(sub.target.elts[0].id) == 1:
                opt_vars.add(sub.target.elts[0].id)
    if bcounts.get(argv_var) != 1 or len(assigns.get(argv_var, ())) != 1:
        return False
    init_assign, init = assigns[argv_var][0], assigns[argv_var][0].value
    if not (isinstance(init, ast.List) and len(init.elts) >= 4 and len(init.elts) % 2 == 0):
        return False
    if not (
        _is_str_call(init.elts[0]) and isinstance(init.elts[1], ast.Constant) and init.elts[1].value == "-I"
        and isinstance(init.elts[2], ast.Constant) and init.elts[2].value == "-B"
        and _is_str_call(init.elts[3]) and isinstance(init.elts[3].args[0], ast.Name)
        and all(_is_long_flag(init.elts[i], set()) and _is_str_call(init.elts[i + 1]) for i in range(4, len(init.elts), 2))
    ):
        return False
    script_var = init.elts[3].args[0].id
    if bcounts.get(script_var) != 1 or len(assigns.get(script_var, ())) != 1:
        return False
    sc_assign, sc = assigns[script_var][0], assigns[script_var][0].value
    if not (
        isinstance(sc, ast.Call) and not sc.args and not sc.keywords and isinstance(sc.func, ast.Attribute) and sc.func.attr == "resolve"
        and isinstance(sc.func.value, ast.Call) and isinstance(sc.func.value.func, ast.Name) and sc.func.value.func.id == "Path"
        and len(sc.func.value.args) == 1 and isinstance(sc.func.value.args[0], ast.Name) and sc.func.value.args[0].id == "__file__"
    ):
        return False
    for sub in ast.walk(fn_scope):
        if isinstance(sub, ast.Name) and sub.id == script_var and sub not in (sc_assign.targets[0], init.elts[3].args[0]):
            return False
        if isinstance(sub, ast.Name) and sub.id == argv_var and sub not in (init_assign.targets[0], call.args[0]):
            par = pmap.get(sub)
            cpar = pmap.get(par) if par is not None else None
            if not (isinstance(sub.ctx, ast.Load) and isinstance(par, ast.Attribute) and par.value is sub and isinstance(cpar, ast.Call) and cpar.func is par and len(cpar.args) == 1 and not cpar.keywords):
                return False
            arg0 = cpar.args[0]
            if not ((par.attr == "append" and _is_long_flag(arg0, set())) or (par.attr == "extend" and isinstance(arg0, ast.Tuple) and len(arg0.elts) == 2 and _is_long_flag(arg0.elts[0], opt_vars) and _is_str_call(arg0.elts[1]))):
                return False
    return True


def _collect_tree_facts(
    tree: ast.Module, *, strict_capabilities: bool = True, module_stem: str = ""
) -> tuple[frozenset[str], frozenset[str], frozenset[str], frozenset[str], list[str]]:
    """Collect `(imported_kill_names, impure_os_sys_names, pure_re_names, private_helpers, capability_errors)`."""
    parent_map = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    call_func_ids = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    attr_value_ids = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    getattr_obj_ids = {id(n.args[0]) for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"getattr", "hasattr"} and len(n.args) >= 2}
    inner_scope_ids = {id(sub) for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) for sub in ast.walk(n) if sub is not n}
    allowed_helper_syms = frozenset().union(*_ALLOWED_LOCAL_FROM_MAP.values())
    hlp_ban_pkgs = {"builtins", "posix", "nt", "operator"} | (set() if module_stem in {"bounded_process", "windows_process", "bounded", "updater_schedule", "_host_exec"} else {"subprocess"})
    imported_kills, bounded_run_names, non_import_bound, store_or_del_names = set(), set(), set(), set()
    name_store_counts: dict[str, int] = {}
    self_method_node_ids, windll_vars = set(), set()
    cap_errors: list[str] = []
    scope_top_stmts: set[int] = {id(s) for s in tree.body}

    class_first_self_arg_ids = {id(stmt.args.args[0]) for cls in ast.walk(tree) if isinstance(cls, ast.ClassDef) for stmt in cls.body if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.args.args and stmt.args.args[0].arg == "self"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            non_import_bound.add(node.name)
            store_or_del_names.add(node.name)
            name_store_counts[node.name] = name_store_counts.get(node.name, 0) + 1
            if isinstance(node, ast.ClassDef):
                for stmt in node.body:
                    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.args.args and stmt.args.args[0].arg == "self":
                        self_method_node_ids.update(id(sub) for sub in ast.walk(stmt))
            else:
                scope_top_stmts.update(id(s) for s in node.body)
        elif isinstance(node, ast.arg):
            non_import_bound.add(node.arg)
            if id(node) not in class_first_self_arg_ids:
                store_or_del_names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            non_import_bound.add(node.id)
            store_or_del_names.add(node.id)
            name_store_counts[node.id] = name_store_counts.get(node.id, 0) + 1
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            non_import_bound.update(node.names)
            store_or_del_names.update(node.names)
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
            non_import_bound.add(node.name)
            store_or_del_names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            non_import_bound.add(node.rest)
            store_or_del_names.add(node.rest)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "WinDLL":
            windll_vars.add(node.targets[0].id)

    all_binding_counts = _count_scope_bindings(tree)
    path_imports: dict[str, list[tuple[int, str, str, bool]]] = {}
    import_sources: dict[str, list[tuple[str, bool]]] = {}
    all_module_aliases: set[str] = set()
    local_module_aliases: set[str] = set()
    stdlib_alias_roots: dict[str, set[str]] = {}
    ctypes_aliases: set[str] = set()
    top_stmt_ids = {id(s) for s in tree.body}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            in_top = id(node) in scope_top_stmts
            for alias in node.names:
                if strict_capabilities and alias.name not in _ALLOWED_EXACT_IMPORTS:
                    cap_errors.append(f"line {node.lineno} `import {alias.name}` is not in storage module allowlist")
                elif not strict_capabilities and (alias.name not in _ALLOWED_HELPER_IMPORTS or alias.name.split(".", 1)[0] in hlp_ban_pkgs):
                    cap_errors.append(f"line {node.lineno} `import {alias.name}` is banned in storage helpers")
                top_pkg = alias.name.split(".", 1)[0]
                bound = alias.asname or top_pkg
                if not strict_capabilities and id(node) not in inner_scope_ids and bound in allowed_helper_syms:
                    cap_errors.append(f"line {node.lineno} module import aliasing export `{bound}` is banned in storage helpers")
                all_module_aliases.add(bound)
                if alias.name in _LOCAL_STORAGE_MODULES:
                    local_module_aliases.add(bound)
                    stdlib_alias_roots.setdefault(bound, set()).add(alias.name)
                else:
                    stdlib_alias_roots.setdefault(bound, set()).add("ntpath" if alias.name == "os.path" and alias.asname else top_pkg)
                if alias.name == "ctypes":
                    ctypes_aliases.add(bound)
                src = "os" if (alias.name == "os" or (alias.asname is None and alias.name == "os.path")) else ("sys" if alias.name == "sys" else ("re" if alias.name == "re" else "other"))
                import_sources.setdefault(bound, []).append((src, in_top))
        elif isinstance(node, ast.ImportFrom):
            lvl, mod = node.level or 0, node.module or ""
            if strict_capabilities and lvl == 0 and mod not in _ALLOWED_FROM_MODULES:
                cap_errors.append(f"line {node.lineno} `from {mod} import ...` is not in storage module allowlist")
            elif strict_capabilities and lvl > 0 and (lvl, mod) not in _ALLOWED_LOCAL_FROM_MAP:
                cap_errors.append(f"line {node.lineno} relative `from {'.' * lvl}{mod} import ...` is not in storage module allowlist")
            for alias in node.names:
                if alias.name == "*":
                    cap_errors.append(f"line {node.lineno} wildcard `from {mod or '.'} import *` is banned in storage modules")
                    continue
                if strict_capabilities:
                    if mod == "typing" and lvl == 0:
                        if alias.name not in _ALLOWED_TYPING_NAMES:
                            cap_errors.append(f"line {node.lineno} `from typing import {alias.name}` is banned in storage modules")
                    elif (lvl, mod) in _ALLOWED_LOCAL_FROM_MAP:
                        if alias.name not in _ALLOWED_LOCAL_FROM_MAP[(lvl, mod)]:
                            cap_errors.append(f"line {node.lineno} `from {'.' * lvl}{mod} import {alias.name}` is not in local storage symbol allowlist")
                    elif lvl == 0 and (mod, alias.name) not in _ALLOWED_STDLIB_FROM_PAIRS:
                        cap_errors.append(f"line {node.lineno} `from {mod} import {alias.name}` is not in storage module allowlist")
                    if alias.name in _REFLECTIVE_FNS or alias.name in _BANNED_ATTR_NAMES or (alias.name.startswith("__") and alias.name.endswith("__")):
                        cap_errors.append(f"line {node.lineno} importing reflective symbol `{alias.name}` is banned in storage modules")
                elif (
                    mod.split(".", 1)[0] in hlp_ban_pkgs
                    or alias.name in (_REFLECTIVE_FNS | {"kill"})
                    or (alias.name == "import_module" and alias.asname is not None)
                    or (alias.name.startswith("__") and alias.name.endswith("__") and (mod, alias.name) != ("__future__", "annotations"))
                    or (lvl == 0 and mod != "typing" and mod.split(".", 1)[0] not in _ALLOWED_HELPER_LOCAL_FROM_PREFIXES and (mod, alias.name) not in _ALLOWED_HELPER_STDLIB_FROM_PAIRS)
                ):
                    cap_errors.append(f"line {node.lineno} `from {mod} import {alias.name}` is banned in storage helpers")
                bound = alias.asname or alias.name
                if (
                    not strict_capabilities and id(node) not in inner_scope_ids and bound in allowed_helper_syms
                    and not (alias.asname is None and mod.rsplit(".", 1)[-1] in {m.rsplit(".", 1)[-1] for _, m in _ALLOWED_LOCAL_FROM_MAP})
                ):
                    cap_errors.append(f"line {node.lineno} re-exporting `{bound}` from `{mod or '.'}` is banned in storage helpers")
                non_import_bound.add(bound)
                path_imports.setdefault(bound, []).append((lvl, mod, alias.name, id(node) in top_stmt_ids))
                if lvl == 0 and mod == "bounded_process" and alias.name == "run":
                    bounded_run_names.add(bound)
                if (lvl == 0 and (mod, alias.name) in _STDLIB_SUBMODULE_IMPORTS) or alias.name in {"storage", "legacy_roots"}:
                    sub_root = _STDLIB_SUBMODULE_IMPORTS.get((mod, alias.name), alias.name)
                    all_module_aliases.add(bound)
                    stdlib_alias_roots.setdefault(bound, set()).add(sub_root)
                if lvl > 0 or mod in _LOCAL_STORAGE_MODULES:
                    local_module_aliases.add(bound)
                if alias.name == "kill":
                    imported_kills.add(bound)
    pure_pathlib_paths = {b for b, entries in path_imports.items() if all_binding_counts.get(b) == 1 and entries == [(0, "pathlib", "Path", True)]}

    impure_os_sys, pure_re = set(non_import_bound), set()
    for bound, entries in import_sources.items():
        srcs = {s for s, _ in entries}
        if not all(t for _, t in entries) or len(srcs) > 1 or srcs not in ({"os"}, {"sys"}):
            impure_os_sys.add(bound)
        if bound not in non_import_bound and entries == [("re", True)]:
            pure_re.add(bound)

    enclosing_fn = {id(sub): stmt for stmt in tree.body if isinstance(stmt, ast.FunctionDef) for sub in ast.walk(stmt)}
    enclosing_call_scope: dict[int, ast.AST] = {}
    def _bind_scopes(cur: ast.AST, active: ast.AST) -> None:
        enclosing_call_scope[id(cur)] = active
        nxt = cur if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)) else active
        for ch in ast.iter_child_nodes(cur):
            _bind_scopes(ch, nxt)
    _bind_scopes(tree, tree)
    bad_dyn_attrs = _BANNED_ATTR_NAMES | {"kill", "name", "platform", "compile", "resolve"}
    def _ok_attr_str(val: object) -> bool:
        return isinstance(val, str) and not (val.startswith("__") and val.endswith("__")) and val not in bad_dyn_attrs
    def _is_safe_attr_var(call_n: ast.AST, expr: ast.AST) -> bool:
        sc = enclosing_call_scope.get(id(call_n))
        if not (isinstance(expr, ast.Name) and isinstance(sc, (ast.FunctionDef, ast.AsyncFunctionDef))):
            return False
        v = expr.id
        if any(isinstance(g, (ast.Global, ast.Nonlocal)) and v in g.names for g in ast.walk(sc)):
            return False
        nst = {id(s) for n in ast.walk(sc) if n is not sc and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) for s in ast.walk(n) if s is not n}
        ctgt = {id(s) for c in ast.walk(sc) if id(c) not in nst and isinstance(c, _COMPREHENSION_TYPES) for g in c.generators for s in ast.walk(g.target)}
        cnt = sum(
            (isinstance(n, ast.arg) and n.arg == v)
            or (n is not sc and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and n.name == v)
            or (isinstance(n, ast.MatchMapping) and n.rest == v)
            or (isinstance(n, ast.Import) and any((a.asname or a.name.split(".", 1)[0]) == v for a in n.names))
            or (isinstance(n, ast.ImportFrom) and any((a.asname or a.name) == v for a in n.names))
            or (isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)) and id(n) not in ctgt and n.id == v)
            for n in ast.walk(sc) if id(n) not in nst
        )
        return cnt == 1 and any(
            id(fn) not in nst and isinstance(fn, ast.For) and isinstance(fn.target, ast.Name) and fn.target.id == v
            and isinstance(fn.iter, ast.Tuple) and fn.iter.elts and all(isinstance(e, ast.Constant) and _ok_attr_str(e.value) for e in fn.iter.elts)
            and any(s is call_n for st in fn.body for s in ast.walk(st))
            for fn in ast.walk(sc)
        )
    h_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_h"]
    updater_h_safe = (
        module_stem == "updater_schedule" and all_binding_counts.get("_h") == 1 and bool(h_calls)
        and all(id(n) in call_func_ids for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id == "_h")
        and all(len(c.args) == 1 and not c.keywords and isinstance(c.args[0], ast.Constant) and _ok_attr_str(c.args[0].value) for c in h_calls)
    )
    explicit_all: set[str] | None = None
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == "__all__" and isinstance(stmt.value, (ast.List, ast.Tuple)):
            explicit_all = {e.value for e in stmt.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    private_helpers = {
        stmt.name for stmt in tree.body
        if explicit_all is not None and isinstance(stmt, ast.FunctionDef) and stmt.name.startswith("_") and not stmt.name.startswith("__")
        and stmt.name not in explicit_all and name_store_counts.get(stmt.name) == 1 and not stmt.decorator_list and not stmt.args.defaults and not any(stmt.args.kw_defaults)
    }

    for node in ast.walk(tree):
        if strict_capabilities and isinstance(node, ast.MatchClass):
            cap_errors.append(f"line {node.lineno} class pattern matching is banned in storage modules")
        elif strict_capabilities and isinstance(node, ast.ClassDef):
            if any(isinstance(sub, (ast.Import, ast.ImportFrom)) for sub in ast.walk(node)):
                cap_errors.append(f"line {node.lineno} class `{node.name}` body/method imports are banned in storage modules")
            if node.keywords:
                cap_errors.append(f"line {node.lineno} class `{node.name}` metaclass/keywords are banned in storage modules")
            for base in node.bases:
                ok_base = (isinstance(base, ast.Name) and base.id in _ALLOWED_CLASS_BASE_NAMES and base.id not in (non_import_bound | all_module_aliases)) or (
                    isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and base.value.id in ctypes_aliases and base.value.id not in non_import_bound and base.attr == "Structure"
                )
                if not ok_base:
                    cap_errors.append(f"line {node.lineno} class `{node.name}` inherits disallowed or shadowed base in storage modules")
        elif not strict_capabilities and isinstance(node, ast.Global) and any(nm in allowed_helper_syms and not nm.isupper() for nm in node.names):
            cap_errors.append(f"line {node.lineno} `global` rebinding of callable export is banned in storage helpers")
        elif not strict_capabilities and id(node) not in inner_scope_ids and (
            (isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id in allowed_helper_syms and not node.id.isupper())
            or (isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and getattr(node, "name", None) in allowed_helper_syms and not node.name.isupper())
            or (isinstance(node, ast.MatchMapping) and node.rest in allowed_helper_syms and not node.rest.isupper())
            or (isinstance(node, ast.FunctionDef) and node.name in allowed_helper_syms and not node.name.isupper() and name_store_counts.get(node.name, 0) > 1)
        ):
            cap_errors.append(f"line {node.lineno} non-function or duplicate binding of callable export is banned in storage helpers")
        elif isinstance(node, ast.Attribute):
            is_dunder = node.attr.startswith("__") and node.attr.endswith("__")
            is_private = node.attr.startswith("_") and not is_dunder
            par = parent_map.get(node)
            ok_self_store = isinstance(node.value, ast.Name) and node.value.id == "self" and "self" not in (store_or_del_names | all_module_aliases | imported_kills) and id(node) in self_method_node_ids
            ok_field_store = node.attr in {"commands", "dwSize", "depths", "argtypes", "restype"} and not (isinstance(node.value, ast.Name) and node.value.id in (all_module_aliases | set(path_imports)))
            if isinstance(node.ctx, (ast.Store, ast.Del)) and (
                is_dunder or node.attr in {"name", "platform", "kill", "compile", "resolve"}
                or (strict_capabilities and not (ok_self_store or ok_field_store))
            ):
                cap_errors.append(f"line {node.lineno} mutating or deleting `.{node.attr}` is banned in storage modules")
            elif (strict_capabilities and node.attr in _BANNED_ATTR_NAMES) or (
                not strict_capabilities and (
                    node.attr in {"modules", "_getframe", "f_builtins", "f_globals", "f_locals", "__dict__", "__builtins__", "os"}
                    or (module_stem not in {"bounded_process", "windows_process", "bounded", "updater_schedule", "_host_exec"} and node.attr in {"system", "popen", "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe", "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe", "posix_spawn", "posix_spawnp"})
                )
            ):
                cap_errors.append(f"line {node.lineno} `.{node.attr}` access is banned in storage modules")
            elif strict_capabilities and is_private:
                ok_self_priv = ok_self_store and node.attr in _ALLOWED_SELF_PRIVATE_ATTRS
                ok_mod_priv = isinstance(node.value, ast.Name) and node.value.id in local_module_aliases and node.value.id not in store_or_del_names and node.attr in _ALLOWED_LOCAL_PRIVATE_ATTRS
                if not (ok_self_priv or ok_mod_priv):
                    cap_errors.append(f"line {node.lineno} private attribute `.{node.attr}` access on external object is banned in storage modules")
            elif is_dunder and (
                (strict_capabilities and (
                    node.attr not in _SAFE_READ_DUNDERS
                    or (node.attr == "__init__" and not (id(node) in call_func_ids and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "super" and "super" not in non_import_bound))
                ))
                or (not strict_capabilities and node.attr not in {"__init__", "__name__", "__cause__", "__context__", "__traceback__", "__dataclass_fields__"} and not (
                    node.attr == "__setattr__" and isinstance(par, ast.Call) and par.func is node and isinstance(node.value, ast.Name) and node.value.id == "object" and "object" not in non_import_bound and par.args and isinstance(par.args[0], ast.Name) and par.args[0].id == "self" and id(node) in self_method_node_ids and "self" not in (store_or_del_names | all_module_aliases | imported_kills)
                ))
            ):
                cap_errors.append(f"line {node.lineno} reflective dunder `.{node.attr}` access is banned in storage modules")
            elif not strict_capabilities and isinstance(node.value, ast.Name) and "os" in stdlib_alias_roots.get(node.value.id, ()):
                extra_os = ({"execve"} if module_stem == "windows_process" else set()) | ({"killpg"} if module_stem in {"bounded_process", "bounded"} else set())
                if node.attr not in (_ALLOWED_HELPER_OS_ATTRS | extra_os):
                    cap_errors.append(f"line {node.lineno} `os.{node.attr}` is outside allowlisted helper OS APIs")
            elif strict_capabilities and ((isinstance(node.value, ast.Name) and node.value.id in windll_vars) or (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "WinDLL")):
                ok_k32_use = id(node) in call_func_ids or (isinstance(par, ast.Attribute) and par.value is node and par.attr in {"argtypes", "restype"} and isinstance(par.ctx, ast.Store))
                if node.attr not in _ALLOWED_KERNEL32_FNS or not ok_k32_use:
                    cap_errors.append(f"line {node.lineno} WinDLL `.{node.attr}` is outside allowlisted or direct kernel32 API calls")
            elif strict_capabilities and isinstance(node.value, ast.Name) and node.value.id in stdlib_alias_roots:
                roots = stdlib_alias_roots[node.value.id]
                if len(roots) != 1 or node.attr not in _ALLOWED_STDLIB_MOD_ATTRS.get(next(iter(roots)), frozenset()):
                    cap_errors.append(f"line {node.lineno} `{node.value.id}.{node.attr}` is outside allowlisted stdlib storage APIs")
                if node.attr == "path" and "os" in roots and id(node) not in attr_value_ids and id(node) not in getattr_obj_ids:
                    cap_errors.append(f"line {node.lineno} first-class `os.path` module reference is banned in storage modules")
            elif strict_capabilities and isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name) and "os" in stdlib_alias_roots.get(node.value.value.id, ()) and node.value.attr == "path" and node.attr not in _ALLOWED_OS_PATH_ATTRS:
                cap_errors.append(f"line {node.lineno} `os.path.{node.attr}` is outside allowlisted path APIs")
            if isinstance(node.ctx, ast.Load) and (node.attr == "kill" or (strict_capabilities and node.attr in {"WinDLL", "Popen"})) and id(node) not in call_func_ids:
                cap_errors.append(f"line {node.lineno} first-class/aliased `.{node.attr}` reference is banned in storage modules")
            elif isinstance(node.ctx, ast.Load) and node.attr in (_REFLECTIVE_FNS | {"import_module"}) and id(node) not in call_func_ids:
                cap_errors.append(f"line {node.lineno} first-class/aliased `.{node.attr}` reference is banned in storage modules")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in private_helpers and id(node) not in call_func_ids:
                private_helpers.discard(node.id)
            if node.id == "__builtins__":
                cap_errors.append(f"line {node.lineno} `__builtins__` access is banned in storage modules")
            elif node.id in (imported_kills | _REFLECTIVE_FNS | {"import_module"}) and id(node) not in call_func_ids:
                cap_errors.append(f"line {node.lineno} first-class/aliased `{node.id}` reference is banned in storage modules")
            elif not strict_capabilities and "os" in stdlib_alias_roots.get(node.id, ()) and id(node) not in attr_value_ids and id(node) not in getattr_obj_ids:
                cap_errors.append(f"line {node.lineno} first-class `os` module reference `{node.id}` is banned in storage helpers")
            elif strict_capabilities:
                if node.id == "type" and id(node) not in call_func_ids:
                    cap_errors.append(f"line {node.lineno} first-class `type` reference is banned in storage modules")
                elif node.id in (ctypes_aliases | windll_vars) and id(node) not in attr_value_ids:
                    cap_errors.append(f"line {node.lineno} first-class `ctypes`/`WinDLL` reference `{node.id}` is banned in storage modules")
                elif (
                    node.id in all_module_aliases and id(node) not in attr_value_ids and id(node) not in getattr_obj_ids
                    and not (
                        node.id == "storage" and stdlib_alias_roots.get(node.id) == {"storage"}
                        and isinstance(parent_map.get(node), ast.Return) and parent_map[node].value is node
                        and (enc_s := enclosing_fn.get(id(node))) is not None and not enc_s.args.args
                        and not any(isinstance(s, ast.Name) and isinstance(s.ctx, (ast.Store, ast.Del)) and s.id == "storage" for s in ast.walk(enc_s))
                    )
                ):
                    cap_errors.append(f"line {node.lineno} first-class module alias `{node.id}` reference is banned in storage modules")
                elif node.id in bounded_run_names and id(node) not in call_func_ids:
                    cap_errors.append(f"line {node.lineno} first-class/aliased `{node.id}` reference is banned in storage modules")
        elif isinstance(node, ast.Call):
            fn = node.func
            if not isinstance(fn, (ast.Name, ast.Attribute)):
                ok_hlp_ind = not strict_capabilities and isinstance(fn, ast.Call) and isinstance(fn.func, ast.Name) and (
                    (fn.func.id == "type" and len(fn.args) == 1)
                    or (fn.func.id == "_h" and len(fn.args) == 1 and isinstance(fn.args[0], ast.Constant) and isinstance(fn.args[0].value, str))
                )
                if not ok_hlp_ind:
                    cap_errors.append(f"line {node.lineno} indirect/chained callee expression is banned in storage modules")
                continue
            is_bare_name = isinstance(fn, ast.Name)
            fn_name = fn.id if is_bare_name else fn.attr
            par = parent_map.get(node)
            enc_cs = enclosing_call_scope.get(id(node))
            in_safe_h = updater_h_safe and isinstance(enc_cs, ast.FunctionDef) and enc_cs.name == "_h" and len(enc_cs.args.args) == 1 and enc_cs.args.args[0].arg == "name" and _count_scope_bindings(enc_cs).get("name") == 1
            if fn_name in {"eval", "exec", "delattr", "vars", "locals", "breakpoint", "attrgetter", "methodcaller", "__import__"}:
                cap_errors.append(f"line {node.lineno} `{fn_name}(...)` is banned in storage modules")
            elif fn_name == "globals":
                ok_glob = not strict_capabilities and is_bare_name and "globals" not in non_import_bound and not node.args and not node.keywords and (
                    (isinstance(par, ast.Subscript) and par.value is node and isinstance(par.ctx, ast.Store))
                    or (in_safe_h and isinstance(par, ast.Subscript) and par.value is node and isinstance(par.slice, ast.Name) and par.slice.id == "name")
                    or (isinstance(par, ast.Attribute) and par.value is node and par.attr == "get" and isinstance(cpar := parent_map.get(par), ast.Call) and cpar.func is par and len(cpar.args) in (1, 2) and not cpar.keywords and isinstance(cpar.args[0], ast.Constant) and _ok_attr_str(cpar.args[0].value))
                )
                if not ok_glob:
                    cap_errors.append(f"line {node.lineno} `globals(...)` namespace reflection is banned in storage modules")
            elif fn_name == "setattr":
                ok_set = not strict_capabilities and module_stem == "bounded" and is_bare_name and "setattr" not in non_import_bound and len(node.args) == 3 and not node.keywords and isinstance(node.args[0], ast.Name) and node.args[0].id not in all_module_aliases and _is_safe_attr_var(node, node.args[1])
                if not ok_set:
                    cap_errors.append(f"line {node.lineno} `setattr(...)` is banned in storage modules")
            elif fn_name == "import_module" and (strict_capabilities or not is_bare_name or all_binding_counts.get("import_module") != 1 or not (len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) and node.args[0].value.startswith("mindie_knowledge."))):
                cap_errors.append(f"line {node.lineno} `import_module(...)` outside static `mindie_knowledge.*` submodule is banned")
            elif not strict_capabilities and fn_name == "getattr":
                arg0_os = len(node.args) >= 1 and isinstance(node.args[0], ast.Name) and "os" in stdlib_alias_roots.get(node.args[0].id, ())
                if not is_bare_name or "getattr" in non_import_bound or not (2 <= len(node.args) <= 3) or node.keywords:
                    cap_errors.append(f"line {node.lineno} dynamic or shadowed `getattr(...)` is banned in storage helpers")
                elif isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                    attr_s = node.args[1].value
                    bad_dunder = attr_s.startswith("__") and attr_s.endswith("__") and attr_s not in {"__cause__", "__context__", "__suppress_context__", "__module__", "__with_libyaml__"}
                    if bad_dunder or (arg0_os and attr_s not in {"O_BINARY", "O_NONBLOCK", "O_NOFOLLOW", "getuid"}) or attr_s == "kill" or attr_s in _BANNED_ATTR_NAMES:
                        cap_errors.append(f"line {node.lineno} `getattr(..., {attr_s!r})` is banned in storage helpers")
                elif arg0_os or not (
                    _is_safe_attr_var(node, node.args[1])
                    or (isinstance(node.args[0], ast.Name) and node.args[0].id in {"signal", "errno"} and all_binding_counts.get(node.args[0].id) == 1 and stdlib_alias_roots.get(node.args[0].id) == {node.args[0].id})
                    or (in_safe_h and isinstance(node.args[0], ast.Name) and node.args[0].id == "_HOST" and isinstance(node.args[1], ast.Name) and node.args[1].id == "name")
                ):
                    cap_errors.append(f"line {node.lineno} dynamic `getattr(...)` is banned in storage helpers")
            elif not strict_capabilities:
                continue
            elif is_bare_name and fn_name in bounded_run_names:
                if not _is_self_dispatch_bounded_run(node, enclosing_fn.get(id(node)), all_binding_counts, pure_pathlib_paths):
                    cap_errors.append(f"line {node.lineno} `bounded_process.run(...)` outside `__file__` self-dispatch is banned in storage modules")
            elif fn_name == "Popen":
                enc = enclosing_fn.get(id(node))
                if enc is None or any(isinstance(s, ast.Constant) and s.value in {"-c", "-m"} for s in ast.walk(enc)) or any(kw.arg in {"shell", "executable"} for kw in node.keywords):
                    cap_errors.append(f"line {node.lineno} `Popen(...)` with shell/inline interpreter flags is banned in storage modules")
            elif is_bare_name and fn_name == "type":
                ok_type_use = "type" not in non_import_bound and len(node.args) == 1 and not isinstance(node.args[0], ast.Starred) and not node.keywords and (
                    (isinstance(par, ast.Attribute) and par.value is node and par.attr == "__name__")
                    or (isinstance(par, ast.Compare) and len(par.ops) == 1 and len(par.comparators) == 1 and isinstance(par.ops[0], (ast.Is, ast.IsNot)) and ((par.left is node and isinstance(par.comparators[0], ast.Name) and par.comparators[0].id in _SCALAR_TYPE_NAMES and par.comparators[0].id not in non_import_bound) or (par.comparators[0] is node and isinstance(par.left, ast.Name) and par.left.id in _SCALAR_TYPE_NAMES and par.left.id not in non_import_bound)))
                )
                if not ok_type_use:
                    cap_errors.append(f"line {node.lineno} first-class or dynamic `type(...)` is banned in storage modules")
            elif fn_name == "WinDLL":
                ok_windll = isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in ctypes_aliases and fn.value.id not in non_import_bound and len(node.args) == 1 and not isinstance(node.args[0], ast.Starred) and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) and node.args[0].value.lower() in {"kernel32", "kernel32.dll"} and all(kw.arg == "use_last_error" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, bool) for kw in node.keywords) and ((isinstance(par, ast.Assign) and len(par.targets) == 1 and isinstance(par.targets[0], ast.Name) and par.value is node) or (isinstance(par, ast.Attribute) and par.value is node and par.attr in _ALLOWED_KERNEL32_FNS))
                if not ok_windll:
                    cap_errors.append(f"line {node.lineno} non-kernel32 or unbound `WinDLL(...)` is banned in storage modules")
            elif fn_name == "getattr":
                if not is_bare_name or "getattr" in non_import_bound or len(node.args) < 2 or len(node.args) > 3 or node.keywords or not isinstance(node.args[1], ast.Constant) or not isinstance(node.args[1].value, str) or node.args[1].value not in _ALLOWED_GETATTR_NAMES:
                    cap_errors.append(f"line {node.lineno} `getattr(...)` outside allowlisted OS/stat attributes is banned in storage modules")

    return frozenset(imported_kills), frozenset(impure_os_sys), frozenset(pure_re), frozenset(private_helpers), cap_errors


def inspect_storage_module_windows_pid_safety(path: Path, *, strict_capabilities: bool = True) -> list[str]:
    """Verify module `path` never calls `os.kill(pid, 0)` outside proven POSIX branches."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imported_kills, impure, pure_re_global, private_helpers, errors = _collect_tree_facts(tree, strict_capabilities=strict_capabilities, module_stem=path.stem)
    proven_posix_helpers: set[str] = set()
    call_sites: dict[str, list[bool]] = {}
    emit_errors = False

    def _visit_expr(
        node: ast.AST, posix_proven: bool, scope_name: str, m_os: frozenset[str], m_sys: frozenset[str], m_re: frozenset[str]
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
            if not emit_errors and isinstance(fn, ast.Name) and fn.id in private_helpers:
                call_sites.setdefault(fn.id, []).append(posix_proven)
            if emit_errors:
                if (isinstance(fn, ast.Name) and fn.id == "compile") or (isinstance(fn, ast.Attribute) and fn.attr == "compile"):
                    if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in m_re):
                        errors.append(f"line {node.lineno} non-regex `compile(...)` is banned in storage modules")
                if strict_capabilities and isinstance(fn, ast.Attribute) and fn.attr == "Popen" and not posix_proven:
                    errors.append(f"line {node.lineno} `{scope_name}` calls `Popen(...)` outside proven POSIX branch in storage modules")
                is_kill_call = (isinstance(fn, ast.Attribute) and (fn.attr == "kill" or fn.attr in imported_kills)) or (isinstance(fn, ast.Name) and fn.id in imported_kills)
                if is_kill_call and not _is_exempt_direct_kill_call(node, imported_kills) and not posix_proven:
                    errors.append(f"line {node.lineno} `{scope_name}` calls unguarded `os.kill(pid, 0)` (guard with `os.name != 'nt'` or use Win32 `OpenProcess`)")
        for child in ast.iter_child_nodes(node):
            _visit_expr(child, posix_proven, scope_name, m_os, m_sys, m_re)

    def _walk_block(
        block: list[ast.stmt], blk_posix: bool, scope_name: str, m_os: frozenset[str], m_sys: frozenset[str], m_re: frozenset[str],
        *, top_block: bool, in_loop: bool = False, is_class_body: bool = False,
        lex_os: frozenset[str] = frozenset(), lex_sys: frozenset[str] = frozenset(), lex_re: frozenset[str] = frozenset(),
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
                fn_pos = cur_pos or (scope_name == "<module>" and stmt.name in proven_posix_helpers)
                _walk_block(stmt.body, fn_pos, stmt.name, child_o, child_s, child_r, top_block=True, in_loop=False)
            elif isinstance(stmt, ast.ClassDef):
                for expr in (*stmt.decorator_list, *getattr(stmt, "type_params", ()), *stmt.bases, *(kw.value for kw in stmt.keywords)):
                    _visit_expr(expr, cur_pos, scope_name, fo, fs, fr)
                _walk_block(stmt.body, cur_pos, stmt.name, child_o, child_s, child_r, top_block=False, in_loop=False, is_class_body=True, lex_os=child_o, lex_sys=child_s, lex_re=child_r)
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
                        c_pos = c_pos or _guard_implications(mc.guard, fo, fs)[0]
                    _walk_block(mc.body, c_pos, scope_name, fo, fs, fr, top_block=False, in_loop=in_loop)
            else:
                for _, val in ast.iter_fields(stmt):
                    if isinstance(val, list) and val and all(isinstance(it, ast.stmt) for it in val):
                        _walk_block(val, cur_pos, scope_name, fo, fs, fr, top_block=False, in_loop=in_loop)
                    elif isinstance(val, list):
                        for it in (x for x in val if isinstance(x, ast.AST)):
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

    for _ in range(3 if private_helpers else 0):
        call_sites.clear()
        _walk_block(tree.body, False, "<module>", frozenset(), frozenset(), frozenset(), top_block=True)
        proven_posix_helpers = {fn for fn in private_helpers if call_sites.get(fn) and all(call_sites[fn])}
    emit_errors = True
    _walk_block(tree.body, False, "<module>", frozenset(), frozenset(), frozenset(), top_block=True)
    return errors


def inspect_helper_windows_pid_safety(path: Path) -> list[str]:
    """Verify helper modules imported by storage modules never call unguarded `os.kill(pid, 0)`."""
    return inspect_storage_module_windows_pid_safety(path, strict_capabilities=False)
