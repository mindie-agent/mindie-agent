#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Zero-dependency MindIE Agent installer for humans and AI agents.

[Role] Detect native hosts, probe `gh` via a disposable `GH_CONFIG_DIR`, verify SHA-256, and
delegate per-host install to `mindie_harness.cli install` from a verified wheelhouse.
[Invariants] Python 3.11+ stdlib only; deterministic UTF-8 JSON; dry-run/empty-auto create zero
directories; no `os.kill`/`torch_npu`/manual `mkstemp`; no state retains `mindie-stage-*`;
every Windows subprocess passes `creationflags=_CREATE_NO_WINDOW`.
[Timeouts & Locks] `gh` 3s; bootstrap 60s; harness 300s; channel 20s; no locks.
[Side-Effect Policy] Read-only detection; real installs write only `cfg_root`/`data_root`.
"""

from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tarfile, tempfile, urllib.error, urllib.parse, urllib.request
from pathlib import Path
SCHEMA, DEFAULT_CHANNEL, HOSTS = "mindie-install/1", "https://github.com/mindie-agent/mindie-agent/releases/latest/download", ("codex", "cc", "kimi", "dsh", "agy", "wb", "oc")
HOST_ALIASES = {"codex": "codex", "cc": "cc", "claude": "cc", "kimi": "kimi", "dsh": "dsh", "agy": "agy", "antigravity": "agy", "wb": "wb", "workbuddy": "wb", "codebuddy": "wb", "oc": "oc", "opencode": "oc"}
MIN_FREE_BYTES, MAX_BUNDLE_BYTES, MAX_RELEASE_BYTES, MAX_SUMS_BYTES = 2_684_354_560, 16 * 1024 * 1024, 1024 * 1024, 256 * 1024
MAX_MEMBERS, MAX_UNPACKED_BYTES, _CHUNK, _CREATE_NO_WINDOW = 64, 32 * 1024 * 1024, 64 * 1024, (0x08000000 if os.name == "nt" else 0)
_MARKERS = {"CODEX_THREAD_ID": "codex", "CODEX_CI": "codex", "CLAUDECODE": "cc", "KIMI_CODE_HOME": "kimi", "DSH_PROFILE": "dsh", "DSH_HOME": "dsh", "AGY_CONVERSATION_ID": "agy", "AGY_APP_DATA_DIR": "agy", "WORKBUDDY_CONFIG_DIR": "wb", "CODEBUDDY_CONFIG_DIR": "wb", "MINDIE_WB_BIN": "wb", "OPENCODE_SESSION_ID": "oc"}
_BINARIES = {"codex": ("codex",), "cc": ("claude",), "kimi": ("kimi",), "dsh": ("dsh",), "agy": ("agy", "antigravity"), "wb": ("wb", "workbuddy", "codebuddy"), "oc": ("opencode",)}
class _ChannelError(Exception):
    def __init__(self, reason): super().__init__(reason); self.reason = reason
def _emit(payload, code=0):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except TimeoutError: raise
    except (AttributeError, OSError, ValueError): pass
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"); return code
def _run_cmd(argv, *, env, timeout):
    return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, check=False, env=env, creationflags=_CREATE_NO_WINDOW)
def _is_winapps_stub(candidate, *, nt=None):
    if not (os.name == "nt" if nt is None else nt): return False
    low = str(candidate).replace("/", "\\").lower()
    return "\\microsoft\\windowsapps\\" in low or ("\\windowsapps\\" in low and candidate.stat().st_size == 0)
def _which_native(name, env=None, *, platform=None):
    environ, nt = dict(os.environ if env is None else env), (platform or os.name) == "nt"
    for entry in environ.get("PATH", "").split(os.pathsep):
        if not entry.strip(): continue
        for ext in ((".exe", ".cmd", ".bat", "") if nt else ("",)):
            candidate = Path(entry) / f"{name}{ext}"
            try:
                if not candidate.is_file() or (not nt and not os.access(candidate, os.X_OK)): continue
                if _is_winapps_stub(candidate, nt=nt): continue
                if nt or not _posix_shim_rejected(candidate): return str(candidate)
            except TimeoutError: raise
            except OSError: continue
    return None

def _posix_shim_rejected(path):
    if path.suffix.lower() in {".exe", ".cmd", ".bat", ".ps1"}: return True
    if not re.match(r"^/mnt/[A-Za-z](?:/|$)", str(path)): return False
    try:
        with path.open("rb") as fh: head = fh.read(512)
    except TimeoutError: raise
    except OSError: return True
    if head.startswith(b"\x7fELF"): return False
    first = head.split(b"\n", 1)[0]
    return not (head.startswith(b"#!") and b"\r" not in first and not re.search(rb"(?:CYGWIN|MINGW|MSYS|cygpath|(?<!\\)\.exe\b|[A-Za-z]:[\\/])", head, re.I))
def _path_exists(path):
    try: return path.exists()
    except TimeoutError: raise
    except OSError: return False
def _roots(env):
    nt = os.name == "nt"
    raw = (env.get("USERPROFILE") or env.get("HOME")) if nt else (env.get("HOME") or env.get("USERPROFILE"))
    home = Path(raw).expanduser() if raw else Path.home()
    cfg = Path(env["MINDIE_CONFIG_HOME"]).expanduser() if env.get("MINDIE_CONFIG_HOME") else (
        Path(env.get("APPDATA") or (home / "AppData/Roaming")) if nt else Path(env.get("XDG_CONFIG_HOME") or (home / ".config"))) / "mindie-agent"
    data = Path(env["MINDIE_DATA_HOME"]).expanduser() if env.get("MINDIE_DATA_HOME") else (
        Path(env.get("LOCALAPPDATA") or (home / "AppData/Local")) if nt else Path(env.get("XDG_DATA_HOME") or (home / ".local/share"))) / "mindie-agent"
    return home, cfg, data

def detect_installed_hosts(env=None):
    environ = dict(os.environ if env is None else env)
    home, cfg, _ = _roots(environ)
    found = {host for key, host in _MARKERS.items() if environ.get(key)}
    found.update(host for host, names in _BINARIES.items() if any(_which_native(name, environ) for name in names))
    paths = {
        "codex": [home / ".codex", cfg / "codex.json"], "cc": [home / ".claude", home / ".config/claude", cfg / "cc.json"],
        "kimi": [home / ".kimi", home / ".config/kimi", cfg / "kimi.json"], "dsh": [home / ".dsh", home / ".config/dsh", cfg / "dsh.json"],
        "agy": [Path("/Applications/Antigravity.app"), home / "Applications/Antigravity.app", home / ".gemini/antigravity", cfg / "agy.json"],
        "wb": [Path("/Applications/WorkBuddy.app"), home / "Applications/WorkBuddy.app", home / ".workbuddy", cfg / "wb.json"],
        "oc": [home / ".config/opencode", home / ".opencode", cfg / "oc.json"],
    }
    found.update(host for host, candidates in paths.items() if any(_path_exists(path) for path in candidates))
    return [host for host in HOSTS if host in found]
def _gh(installed, authenticated, account, status, tier):
    return {"gh_installed": installed, "gh_authenticated": authenticated, "gh_account": account, "gh_probe_status": status, "recommended_tier": tier}
def probe_gh_status(env=None, *, offline=False, timeout=3.0):
    environ = dict(os.environ if env is None else env)
    gh_bin = _which_native("gh", environ)
    if not gh_bin: return _gh(False, False, None, "not_installed", "local-only")
    if offline: return _gh(True, False, None, "skipped_offline", "local-only")
    home, _, _ = _roots(environ)
    if environ.get("GH_CONFIG_DIR"): gh_cfg = Path(environ["GH_CONFIG_DIR"]).expanduser()
    elif os.name == "nt": gh_cfg = Path(environ.get("APPDATA") or (home / "AppData/Roaming")) / "GitHub CLI"
    else: gh_cfg = Path(environ.get("XDG_CONFIG_HOME") or (home / ".config")) / "gh"
    try:
        with tempfile.TemporaryDirectory(prefix="mindie-gh-cfg-") as tmp_dir:
            for name in ("hosts.yml", "config.yml"):
                try:
                    source = gh_cfg / name
                    if source.is_file() and source.stat().st_size <= 65536:
                        fd = os.open(Path(tmp_dir) / name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                        with os.fdopen(fd, "wb") as handle: handle.write(source.read_bytes())
                except TimeoutError: raise
                except OSError: pass
            proc = _run_cmd([gh_bin, "api", "--hostname", "github.com", "user", "--jq", ".login"],
                            env={**environ, "GH_CONFIG_DIR": tmp_dir, "XDG_STATE_HOME": tmp_dir,
                                 "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1"}, timeout=timeout)
    except subprocess.TimeoutExpired: return _gh(True, False, None, "timeout", "local-only")
    except TimeoutError: raise
    except OSError: return _gh(True, False, None, "unauthenticated", "local-only")
    login = proc.stdout.strip()
    if proc.returncode == 0 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", login): return _gh(True, True, login, "authenticated", "contribute")
    return _gh(True, False, None, "unauthenticated", "local-only")
def _next_questions(tier):
    privacy = ["contribute", "local-only", "read-only"] if tier == "contribute" else ["local-only", "read-only", "contribute"]
    return [{"id": "workspace_roots", "recommended": "init_vllm_ascend_workspace", "options": ["init_vllm_ascend_workspace", "use_current_directory", "select_existing_directory"]},
            {"id": "privacy_tier", "recommended": tier, "options": privacy},
            {"id": "optional_ssh_npu_host", "recommended": "connect_now", "options": ["connect_now", "skip_for_now"], "password_safe_cli_flag": "--password"}]
def _base_payload(detected, gh):
    return {"schema": SCHEMA, "detected_hosts": detected, "configured_hosts": [], **gh,
            "next_questions": _next_questions(gh["recommended_tier"]), "reportable": False}
def _fail(base, reason, **extra):
    return _emit({**base, "status": "error", "reason": reason, **extra}, 1)
class _HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not str(newurl).lower().startswith("https://"): raise _ChannelError("insecure_channel_url")
        return super().redirect_request(req, fp, code, msg, headers, newurl)
def _open_channel(base, name):
    if base.startswith("https://"):
        try: return urllib.request.build_opener(_HttpsOnlyRedirect).open(f"{base.rstrip('/')}/{name}", timeout=20.0)
        except urllib.error.HTTPError as exc:
            reason = "not_found" if exc.code == 404 else "download_failed"
            raise _ChannelError("checksum_manifest_missing" if name == "SHA256SUMS" and exc.code == 404 else reason) from exc
        except TimeoutError: raise
        except (urllib.error.URLError, OSError) as exc: raise _ChannelError("download_failed") from exc
    path = (Path(urllib.request.url2pathname(urllib.parse.urlparse(base).path)) if base.startswith("file://") else Path(base).expanduser()) / name
    try: return open(path, "rb") if path.is_file() else None
    except TimeoutError: raise
    except OSError as exc: raise _ChannelError("download_failed") from exc
def _read_stream(base, name, cap):
    handle = _open_channel(base, name)
    if handle is None: return None
    data = bytearray()
    try:
        while chunk := handle.read(_CHUNK):
            if len(data) + len(chunk) > cap: raise _ChannelError("bundle_too_large" if name.endswith(".tar.gz") else "channel_file_too_large")
            data.extend(chunk)
    except TimeoutError: raise
    except OSError as exc: raise _ChannelError("download_failed") from exc
    finally: handle.close()
    return bytes(data)
def _load_sums(base):
    raw = _read_stream(base, "SHA256SUMS", MAX_SUMS_BYTES)
    if raw is None: raise _ChannelError("checksum_manifest_missing")
    sums = {}
    for raw_line in raw.decode("utf-8", "replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"): continue
        match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", line)
        if not match: raise _ChannelError("malformed_checksum_manifest")
        if match.group(2).strip() in sums: raise _ChannelError("duplicate_checksum_filename")
        sums[match.group(2).strip()] = match.group(1).lower()
    if not {"release-channel.json", "mindie-wheels-bundle.tar.gz"} <= set(sums): raise _ChannelError("checksum_manifest_incomplete")
    return sums
def _download_file(base, name, cap, dest, sums):
    handle = _open_channel(base, name)
    if handle is None: raise _ChannelError("not_found")
    digest, size, tmp = hashlib.sha256(), 0, dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "wb") as out:
            while chunk := handle.read(_CHUNK):
                size += len(chunk)
                if size > cap: raise _ChannelError("bundle_too_large" if name.endswith(".tar.gz") else "channel_file_too_large")
                digest.update(chunk); out.write(chunk)
        if digest.hexdigest() != sums[name]: raise _ChannelError("checksum_mismatch")
        os.replace(tmp, dest)
    except TimeoutError: raise
    except _ChannelError: raise
    except OSError as exc: raise _ChannelError("download_failed") from exc
    finally:
        handle.close()
        try: tmp.unlink(missing_ok=True)
        except TimeoutError: raise
        except OSError: pass
def _norm_pkg(name): return re.sub(r"[-_.]+", "-", str(name or "")).lower()
def _extract_bundle(bundle, wheels):
    wheels.mkdir(mode=0o700)
    root, seen, total, extracted = wheels.resolve(), set(), 0, {}
    with tarfile.open(bundle, "r:gz") as archive:
        for count, member in enumerate(archive, start=1):
            name, basename = member.name, Path(member.name).name
            if (count > MAX_MEMBERS or not name or name.startswith(("/", "\\")) or ".." in Path(name).parts or "\\" in name or ":" in name
                    or member.issym() or member.islnk() or member.isfifo() or member.isdev()):
                raise _ChannelError("bundle_member_limit" if count > MAX_MEMBERS else "unsafe_bundle_member")
            if member.isdir(): continue
            stem = basename.split(".", 1)[0].upper()
            if not member.isfile() or basename.lower() in seen or re.fullmatch(r"CON|PRN|AUX|NUL|(?:COM|LPT)[1-9]", stem):
                raise _ChannelError("duplicate_bundle_member" if basename.lower() in seen else "unsafe_bundle_member")
            seen.add(basename.lower())
            if not basename.lower().endswith(".whl") and basename not in {"requirements.lock", "requirements.txt", "bundle-manifest.json", "SHA256SUMS"}: raise _ChannelError("unsafe_bundle_member")
            total += member.size
            if total > MAX_UNPACKED_BYTES: raise _ChannelError("bundle_too_large")
            target, source = (wheels / name).resolve(), archive.extractfile(member)
            if root not in target.parents or source is None: raise _ChannelError("unsafe_bundle_member")
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with source, open(target, "wb") as out:
                while chunk := source.read(_CHUNK): digest.update(chunk); out.write(chunk)
            if basename.lower().endswith(".whl"): extracted[basename] = (target, digest.hexdigest())
    manifest_file = wheels / "bundle-manifest.json"
    req_file = next((wheels / n for n in ("requirements.txt", "requirements.lock") if (wheels / n).is_file()), None)
    if not manifest_file.is_file() and req_file is None: raise _ChannelError("unsafe_bundle_member")
    harness_name = None
    if manifest_file.is_file():
        try: bm = json.loads(manifest_file.read_text(encoding="utf-8"))
        except ValueError as exc: raise _ChannelError("unsafe_bundle_member") from exc
        rows = bm.get("wheels") if isinstance(bm, dict) else None
        if not isinstance(rows, list) or not rows: raise _ChannelError("unsafe_bundle_member")
        allowed = {r.get("filename"): r.get("sha256") for r in rows if isinstance(r, dict)}
        if set(extracted) != set(allowed) or any(extracted[k][1] != allowed[k] for k in extracted):
            raise _ChannelError("unsafe_bundle_member")
        harness_name = next((r.get("filename") for r in rows if isinstance(r, dict) and _norm_pkg(r.get("package")) == "mindie-harness"), None)
    if req_file is not None:
        pinned = {}
        for raw_line in req_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"): continue
            m = re.match(r"^([A-Za-z0-9._-]+)(?:\[[^\]]+\])?==(\S+)$", line)
            if not m: raise _ChannelError("unsafe_bundle_member")
            pinned[_norm_pkg(m.group(1))] = m.group(2)
        for fname in extracted:
            parts = fname.split("-")
            if len(parts) < 5 or pinned.get(_norm_pkg(parts[0])) != parts[1]: raise _ChannelError("unsafe_bundle_member")
            if _norm_pkg(parts[0]) == "mindie-harness": harness_name = harness_name or fname
    if not harness_name or harness_name not in extracted: raise _ChannelError("harness_wheel_missing")
    return [extracted[harness_name][0]]

def _bootstrap(stage, wheel, uv_bin, host_py, env, offline):
    boot = stage / "bootstrap-venv"
    venv_cmd = [uv_bin, "venv", "--python", str(host_py), *(["--offline"] if offline else []), str(boot)]
    pip_cmd = [uv_bin, "pip", "install", "--python", str(boot / ("Scripts/python.exe" if os.name == "nt" else "bin/python")),
               "--offline", "--no-index", "--no-deps", str(wheel)]
    if _run_cmd(venv_cmd, env=env, timeout=60.0).returncode or _run_cmd(pip_cmd, env=env, timeout=60.0).returncode:
        raise _ChannelError("bootstrap_failed")
    return Path(pip_cmd[4])

def _rewrite_channel_ref(path, old, new):
    if not path.is_file(): return
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError: return
    if not isinstance(data, dict): return
    changed = False
    for obj in (data, data.get("channel") if isinstance(data.get("channel"), dict) else None):
        if obj and obj.get("channel_base_url") in {old, old.replace("\\", "/")}: obj["channel_base_url"] = new; changed = True
    if not changed: return
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try: tmp.unlink(missing_ok=True)
        except TimeoutError: raise
        except OSError: pass
def _install_from_stage(stage, targets, channel, cfg_root, data_root, run_env, uv_bin, host_py, offline, explicit, configured, failed, warnings):
    sums = _load_sums(channel)
    _download_file(channel, "release-channel.json", MAX_RELEASE_BYTES, stage / "release-channel.json", sums)
    try: manifest = json.loads((stage / "release-channel.json").read_bytes())
    except ValueError as exc: raise _ChannelError("invalid_release_channel") from exc
    if not isinstance(manifest, dict): raise _ChannelError("invalid_release_channel")
    version = str(manifest.get("current_patch_version") or manifest.get("product_version") or manifest.get("version") or "").strip()
    bundle_base = (f"{channel.rsplit('/releases/latest/download', 1)[0]}/releases/download/v{version.lstrip('v')}"
                   if not explicit and channel.endswith("/releases/latest/download") and version else channel)
    try: _download_file(bundle_base, "mindie-wheels-bundle.tar.gz", MAX_BUNDLE_BYTES, stage / "mindie-wheels-bundle.tar.gz", sums)
    except _ChannelError as exc:
        if exc.reason != "not_found" or bundle_base == channel: raise
        _download_file(channel, "mindie-wheels-bundle.tar.gz", MAX_BUNDLE_BYTES, stage / "mindie-wheels-bundle.tar.gz", sums)
    (stage / "SHA256SUMS").write_text("".join(f"{d}  {n}\n" for n, d in sorted(sums.items())), encoding="utf-8")
    boot_py = _bootstrap(stage, _extract_bundle(stage / "mindie-wheels-bundle.tar.gz", stage / "wheels")[-1], uv_bin, host_py, run_env, offline)
    for target in targets:
        try:
            proc = _run_cmd([str(boot_py), "-I", "-X", "utf8", "-m", "mindie_harness.cli", "install", "--host", target,
                             "--channel-base-url", str(stage), *(["--offline"] if offline else [])], env=run_env, timeout=300.0)
        except subprocess.TimeoutExpired:
            failed[target] = {"reason": "install_timeout"}; continue
        except TimeoutError: raise
        except OSError as exc:
            failed[target] = {"reason": "install_io_error", "error_type": type(exc).__name__}; continue
        try: payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except ValueError: payload = {}
        if proc.returncode == 0 and target in (payload.get("configured_hosts") or []):
            host_warns = []
            if payload.get("receipt_unconfirmed") or payload.get("receipt_warning"):
                host_warns.append(str(payload.get("receipt_warning") or "child_receipt_unconfirmed"))
            for rpath in (cfg_root / f"{target}.json", data_root / "state" / target / "channel-cache.json"):
                try: _rewrite_channel_ref(rpath, str(stage), channel)
                except TimeoutError: raise
                except OSError as exc: host_warns.append(type(exc).__name__)
            bind_err = _ensure_host_knowledge_binding(target, cfg_root / f"{target}.json", run_env)
            if bind_err is not None:
                failed[target] = bind_err; continue
            configured.append(target)
            if host_warns:
                warnings[target] = host_warns[0] if len(host_warns) == 1 else "; ".join(host_warns)
        else:
            r = payload.get("reason") or ((payload.get("runtimes") or {}).get(target) or {}).get("reason") or "harness_install_failed"
            failed[target] = {"reason": str(r), "returncode": proc.returncode}
    return configured, failed, warnings
_CANONICAL_DOMAINS = frozenset({"vllm-ascend", "operators", "xllm", "mindie-sd", "infer-core",
                                "infer-distributed", "infer-observability", "infer-ops-compat", "agent-engineering"})
def _ensure_host_knowledge_binding(target, cfg_path, run_env):
    if not cfg_path.is_file(): return {"reason": "host_config_missing"}
    try: cfg_doc = json.loads(cfg_path.read_text(encoding="utf-8"))
    except TimeoutError: raise
    except (OSError, ValueError): return {"reason": "invalid_host_config"}
    if not isinstance(cfg_doc, dict): return {"reason": "invalid_host_config"}
    runtime_py = cfg_doc.get("python")
    if not isinstance(runtime_py, str) or not runtime_py.strip() or not _path_exists(Path(runtime_py)):
        return {"reason": "runtime_python_missing"}
    code = ("import importlib.util as u, json, pathlib, sys\n"
            "r = u.find_spec('mindie_harness.runtime')\n"
            "if r is None or r.submodule_search_locations is None or u.find_spec('mindie_harness.runtime.knowledge_binding') is None:\n"
            "    print(json.dumps({'status': 'legacy'})); raise SystemExit(0)\n"
            "from mindie_harness.paths import ProfileRef\n"
            "from mindie_harness.runtime.knowledge_binding import ensure_knowledge_binding\n"
            "print(json.dumps(ensure_knowledge_binding(ProfileRef.resolve(sys.argv[1], config_path=pathlib.Path(sys.argv[2])))))\n")
    try: proc = _run_cmd([runtime_py, "-I", "-X", "utf8", "-c", code, target, str(cfg_path)], env=run_env, timeout=120.0)
    except subprocess.TimeoutExpired: return {"reason": "install_timeout"}
    except TimeoutError: raise
    except OSError as exc: return {"reason": "install_io_error", "error_type": type(exc).__name__}
    if proc.returncode != 0: return {"reason": "knowledge_binding_failed", "returncode": proc.returncode}
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    try: res = json.loads(lines[-1]) if lines else None
    except ValueError: res = None
    if not isinstance(res, dict): return {"reason": "knowledge_binding_failed"}
    if res.get("status") == "legacy": return None
    if res.get("status") != "configured":
        return {"reason": str(res.get("reason") or "knowledge_binding_failed"), "binding_status": str(res.get("status") or "")}
    try: updated = json.loads(cfg_path.read_text(encoding="utf-8"))
    except TimeoutError: raise
    except (OSError, ValueError): return {"reason": "invalid_host_config"}
    eng = updated.get("engine_config") if isinstance(updated, dict) else None
    doms = updated.get("domain_configs") if isinstance(updated, dict) else None
    if (not isinstance(eng, str) or not _path_exists(Path(eng)) or not isinstance(doms, dict)
            or not (_CANONICAL_DOMAINS <= set(doms))
            or any(not isinstance(doms[d], str) or not _path_exists(Path(doms[d])) for d in _CANONICAL_DOMAINS)):
        return {"reason": "knowledge_domains_incomplete"}
    return None
def _deepest_existing(path):
    current = path.expanduser()
    while not _path_exists(current) and current != current.parent: current = current.parent
    return current.resolve()
def _same_volume(left, right):
    try: return _deepest_existing(left).stat().st_dev == _deepest_existing(right).stat().st_dev
    except TimeoutError: raise
    except OSError: return False
def _on_drvfs(path):
    mountinfo, target = Path("/proc/self/mountinfo"), _deepest_existing(path)
    try: lines = mountinfo.read_text(encoding="utf-8", errors="replace").splitlines()
    except TimeoutError: raise
    except OSError: return False
    best = None
    for line in lines:
        if " - " not in line: continue
        left_p, right_p = [seg.split() for seg in line.split(" - ", 1)]
        if len(left_p) < 6 or len(right_p) < 2: continue
        mount = Path(re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), left_p[4]))
        if (target == mount or mount == Path("/") or str(target).startswith(str(mount).rstrip("/") + "/")) and (
                best is None or len(str(mount)) >= len(str(best[0]))): best = (mount, right_p[0].lower(), f"{left_p[5]},{' '.join(right_p[1:])}".lower())
    return bool(best) and (best[1] in {"drvfs", "wslfs"} or (best[1] == "9p" and "drvfs" in best[2]))
def _host_python(env):
    exe = Path(sys.executable)
    try:
        if exe.is_file() and exe.stat().st_size > 0 and not _is_winapps_stub(exe): return exe
    except TimeoutError: raise
    except OSError: pass
    found = _which_native("python3", env) or _which_native("python", env)
    return Path(found) if found else None

def main(argv=None):
    environ = dict(os.environ)
    parser = argparse.ArgumentParser(prog="install.py", description="Install MindIE Agent into detected hosts.")
    parser.add_argument("--host", default="auto"); parser.add_argument("--channel-base-url", default=None)
    parser.add_argument("--offline", action="store_true"); parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    requested = (args.host or "auto").strip().lower()
    if requested != "auto" and requested not in HOST_ALIASES:
        return _emit({"schema": SCHEMA, "status": "error", "reason": "invalid_host", "host": requested, "reportable": False}, 1)
    raw_base = (args.channel_base_url or environ.get("MINDIE_CHANNEL_BASE_URL") or DEFAULT_CHANNEL).strip().rstrip("/")
    explicit = bool(args.channel_base_url or environ.get("MINDIE_CHANNEL_BASE_URL"))
    lowered = raw_base.lower()
    if lowered.startswith("http://") or ("://" in lowered and not lowered.startswith(("https://", "file://"))):
        return _emit({"schema": SCHEMA, "status": "error", "reason": "insecure_channel_url", "reportable": False}, 1)
    if not lowered.startswith(("https://", "file://")): raw_base = str(Path(raw_base).expanduser().resolve())
    detected = detect_installed_hosts(environ)
    targets = detected if requested == "auto" else [HOST_ALIASES[requested]]
    if args.dry_run or not targets:
        gh_bin = _which_native("gh", environ)
        st = ("skipped_dry_run" if args.dry_run else "skipped_no_hosts") if gh_bin else "not_installed"
        base = _base_payload(detected, _gh(bool(gh_bin), False, None, st, "local-only"))
        return _emit({**base, "status": "dry_run" if args.dry_run else "no_hosts", "planned_hosts": targets}, 0)
    gh = probe_gh_status(environ, offline=args.offline)
    base = _base_payload(detected, gh)
    if args.offline and lowered.startswith("https://"): return _fail(base, "offline_remote_channel")
    cfg_root, data_root = _roots(environ)[1:]
    if sys.platform == "linux" and any(_on_drvfs(root) for root in (data_root, cfg_root)): return _fail(base, "drvfs_unsafe_state_root")
    try:
        if shutil.disk_usage(_deepest_existing(data_root)).free < MIN_FREE_BYTES: return _fail(base, "insufficient_disk_space")
    except TimeoutError: raise
    except OSError: return _fail(base, "insufficient_disk_space")
    run_env = dict(environ)
    if not environ.get("UV_CACHE_DIR") or not _same_volume(Path(environ["UV_CACHE_DIR"]), data_root):
        run_env["UV_CACHE_DIR"] = str(data_root / ".uv-cache")
    uv_bin = _which_native("uv", run_env)
    if not uv_bin: return _fail(base, "uv_not_found")
    host_py = _host_python(run_env)
    if host_py is None: return _fail(base, "python_not_found")
    configured, failed, warnings = [], {}, {}
    def _preserve_or_fail(reason, **extra):
        if not configured: return _fail(base, reason, **extra)
        for target in targets:
            if target not in configured and target not in failed:
                failed[target] = {"reason": reason, **extra}
        if not failed: warnings["_stage_cleanup"] = extra.get("error_type") or reason
        out = {**base, "status": "installed" if not failed else "partial_error", "configured_hosts": configured}
        if warnings: out.update({"receipt_warning": warnings, "receipt_unconfirmed": True})
        if failed: out["failed_hosts"] = failed
        return _emit(out, 0 if not failed else 1)
    try:
        data_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix="mindie-stage-", dir=str(data_root)) as stage_str:
            _install_from_stage(Path(stage_str), targets, raw_base, cfg_root, data_root,
                                run_env, uv_bin, host_py, args.offline, explicit, configured, failed, warnings)
    except _ChannelError as exc: return _preserve_or_fail(exc.reason)
    except (subprocess.TimeoutExpired, TimeoutError): return _preserve_or_fail("install_timeout")
    except (OSError, tarfile.TarError) as exc: return _preserve_or_fail("install_io_error", error_type=type(exc).__name__)
    status = "installed" if not failed else ("partial_error" if configured else "error")
    payload = {**base, "status": status, "configured_hosts": configured}
    if warnings: payload.update({"receipt_warning": warnings, "receipt_unconfirmed": True})
    if failed: payload["failed_hosts"] = failed
    return _emit(payload, 0 if not failed else 1)

if __name__ == "__main__":
    raise SystemExit(main())
