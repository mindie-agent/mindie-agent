"""Unit contracts for the lean code/doc hygiene gate across code and corpus repositories.

[Role]
Covers legacy/shadow Python filenames, strict `Upstream-ABI:` version families, orphan and
dead-cycle import graphs, Hatch/entrypoint/`__main__`/launcher roots, living-doc relative
links/anchors/inline paths, Hub published release indexes, bilingual counterparts, and H2
section symmetry.

[Invariants]
- Every fixture is a Tier-0 synthetic checkout under an isolated temporary directory; real Git
  inventory is exercised only by a dedicated local `git init` case.
- Host environment variables are isolated exactly as in the other gate suites.

[Timeouts & Locks]
- Pure local parsing (`< 3s` total); the single Git fixture uses no network and no locks.

[Side-Effect Policy]
- Writes only inside `tempfile.TemporaryDirectory` cleaned up after each test.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import code_doc_hygiene_gate as gate  # noqa: E402

_MAIN_GUARD = '\nif __name__ == "__main__":\n    pass\n'


class CodeDocHygieneGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="mindie-code-doc-hygiene-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        env = {
            "HOME": str(self.root / "home"),
            "USERPROFILE": str(self.root / "home"),
            "APPDATA": str(self.root / "appdata"),
            "LOCALAPPDATA": str(self.root / "localappdata"),
            "XDG_CONFIG_HOME": str(self.root / "xdg-config"),
            "XDG_DATA_HOME": str(self.root / "xdg-data"),
            "MINDIE_CONFIG_HOME": str(self.root / "mindie-config"),
            "MINDIE_DATA_HOME": str(self.root / "mindie-data"),
            "MINDIE_DIAGNOSTICS_ROOT": str(self.root / "diagnostics"),
            "REMOTE_DEV_AUTH_DIR": str(self.root / "remote-auth"),
            "UV_CACHE_DIR": str(self.root / "uv-cache"),
            "TMPDIR": str(self.root / "tmp"),
        }
        (self.root / "tmp").mkdir(parents=True, exist_ok=True)
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, repo: Path, rel: str, text: str = "") -> Path:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def repo(self, name: str, version: str | None = "0.1.5", *, pyproject: bool = True) -> Path:
        repo = self.root / name
        (repo / ".git").mkdir(parents=True)
        if pyproject and version:
            self.write(repo, "pyproject.toml", f'[project]\nname = "mindie-{name}"\nversion = "{version}"\n')
        self.write(repo, "README.md", "# Repository\n\n## Overview\n")
        self.write(repo, "README.en.md", "# Repository\n\n## Overview\n")
        return repo

    def verify(self, repo: Path, name: str, **kwargs) -> list[str]:
        return gate.verify_code_doc_hygiene([self.root], required_repos=[name], **kwargs)

    def hub(self) -> Path:
        hub = self.root / "mindie-agent"
        (hub / ".git").mkdir(parents=True)
        self.write(hub, "README.md", "# Hub\n\n## Overview\n\n[0.1.0](docs/releases/0.1.0.md)\n")
        self.write(hub, "README.en.md", "# Hub\n\n## Overview\n\n[0.1.0](docs/releases/0.1.0.en.md)\n")
        self.write(hub, "CONTRIBUTING.md", "# Contributing\n\n## Process\n")
        self.write(hub, "CONTRIBUTING.en.md", "# Contributing\n\n## Process\n")
        self.write(hub, "docs/README.md", "# Docs\n\n## Releases\n\n[0.1.0](releases/0.1.0.md) · [EN](releases/0.1.0.en.md)\n")
        self.write(hub, "docs/README.en.md", "# Docs\n\n## Releases\n\n[0.1.0 EN](releases/0.1.0.en.md) · [ZH](releases/0.1.0.md)\n")
        self.write(hub, "docs/releases/0.1.0.md", "# 0.1.0\n")
        self.write(hub, "docs/releases/0.1.0.en.md", "# 0.1.0\n")
        self.write(hub, "docs/releases/0.1.9.md", "# failed unpublished\n")
        self.write(hub, "docs/releases/0.1.9.en.md", "# failed unpublished\n")
        self.write(hub, ".github/scripts/existing_gate.py", f"VALUE = 1{_MAIN_GUARD}")
        self.write(
            hub,
            "channels/0.1.json",
            json.dumps({
                "patch_releases": [
                    {"patch_version": "0.1.0", "status": "published"},
                    {"patch_version": "0.1.9", "status": "failed_unpublished"},
                ]
            }),
        )
        return hub

    # ------------------------------------------------------------------ Check A
    def test_legacy_copy_and_unproven_version_shadows_are_rejected(self) -> None:
        repo = self.repo("harness", "0.1.5")
        package = "mindie_harness"
        self.write(repo, f"{package}/__init__.py", "from . import router, router_v2\n")
        self.write(repo, f"{package}/widget_legacy.py", f"VALUE = 1{_MAIN_GUARD}")
        self.write(repo, f"{package}/widget_fallback.py", f"VALUE = 1{_MAIN_GUARD}")
        self.write(repo, f"{package}/tensor.py", "VALUE = 1\n")
        self.write(repo, f"{package}/tensor_copy.py", f"VALUE = 1{_MAIN_GUARD}")
        self.write(repo, f"{package}/router.py", "def route():\n    return 1\n")
        self.write(repo, f"{package}/router_v2.py", f"VALUE = 2{_MAIN_GUARD}")
        errors = self.verify(repo, "harness")
        self.assertTrue(any("widget_legacy.py" in e and "legacy/shadow" in e for e in errors), errors)
        self.assertTrue(any("widget_fallback.py" in e for e in errors), errors)
        self.assertTrue(any("tensor_copy.py" in e and "shadow copy" in e for e in errors), errors)
        self.assertTrue(any("router_v2.py" in e and "Upstream-ABI" in e for e in errors), errors)

    def test_standalone_versioned_and_unpaired_copy_modules_are_accepted(self) -> None:
        repo = self.repo("harness", "0.1.5")
        package = "mindie_harness"
        self.write(repo, f"{package}/__init__.py", "")
        self.write(repo, f"{package}/paged_mla_host_v2.py", f"VALUE = 2{_MAIN_GUARD}")
        self.write(repo, f"{package}/tensor_copy.py", f"VALUE = 1{_MAIN_GUARD}")
        self.assertEqual(self.verify(repo, "harness"), [])

    def test_distinct_ast_grounded_abi_family_is_accepted(self) -> None:
        repo = self.repo("sim", "0.9.19")
        symbols = [f"aclnnFusedInferAttentionScoreV{index}" for index in range(1, 5)]
        self.write(repo, "src/mindie_sim/__init__.py", "from . import ops\n")
        imports = "\n".join(f"from .fia_v{i} import {symbol}" for i, symbol in enumerate(symbols, 1))
        self.write(repo, "src/mindie_sim/ops/__init__.py", imports + "\n")
        for index, symbol in enumerate(symbols, 1):
            self.write(
                repo,
                f"src/mindie_sim/ops/fia_v{index}.py",
                f'"""CANN FIA multi-version op.\n\nUpstream-ABI: {symbol}\n"""\n'
                f"from vendor import {symbol}\n\ndef call_{index}():\n    return {symbol}()\n",
            )
        self.assertEqual(self.verify(repo, "sim"), [])

    def test_fake_or_duplicate_upstream_abi_symbols_are_rejected(self) -> None:
        repo = self.repo("harness", "0.1.5")
        package = "mindie_harness"
        self.write(repo, f"{package}/__init__.py", "from . import router, router_v2, router_v3\n")
        self.write(repo, f"{package}/router.py", "def route():\n    return 1\n")
        self.write(
            repo,
            f"{package}/router_v2.py",
            '"""Version 2.\n\nUpstream-ABI: aclnnMissingKernel\n"""\ndef unrelated():\n    return 1\n',
        )
        self.write(repo, f"{package}/router_v3.py", '"""Version 3.\n\nUpstream-ABI: genericV3\n"""\nVALUE = 3\n')
        errors = self.verify(repo, "harness")
        self.assertTrue(any("router_v2.py" in e and "not referenced" in e for e in errors), errors)
        self.assertTrue(any("router_v3.py" in e and "Upstream-ABI" in e for e in errors), errors)

        self.write(
            repo,
            f"{package}/router_v3.py",
            '"""Version 3.\n\nUpstream-ABI: aclnnSharedKernelV1\n"""\nfrom vendor import aclnnSharedKernelV1\n',
        )
        self.write(
            repo,
            f"{package}/router_v2.py",
            '"""Version 2.\n\nUpstream-ABI: aclnnSharedKernelV1\n"""\nfrom vendor import aclnnSharedKernelV1\n',
        )
        errors = self.verify(repo, "harness")
        self.assertTrue(any("duplicates Upstream-ABI" in e for e in errors), errors)

        # Prefix collision (`aclnnFoo` vs `aclnnFooBar`) and generic terminal (`vendor/default`) must fail
        self.write(
            repo,
            f"{package}/router_v2.py",
            '"""Version 2.\n\nUpstream-ABI: aclnnFoo\n"""\nfrom vendor import aclnnFooBar\n',
        )
        self.write(
            repo,
            f"{package}/router_v3.py",
            '"""Version 3.\n\nUpstream-ABI: vendor/default\n"""\ndef fn(default: int = 1) -> int:\n    return default\n',
        )
        errors = self.verify(repo, "harness")
        self.assertTrue(any("router_v2.py" in e and "not referenced" in e for e in errors), errors)
        self.assertTrue(any("router_v3.py" in e and "Upstream-ABI" in e for e in errors), errors)

    # ------------------------------------------------------------------ Check B
    def test_orphan_modules_and_dead_mutual_import_cycle_are_rejected(self) -> None:
        repo = self.repo("harness", "0.1.5")
        package = "mindie_harness"
        self.write(repo, f"{package}/__init__.py", 'import json\nfrom pathlib import Path\nOLD = Path("retired") / "handler.py"\n')
        self.write(repo, f"{package}/orphan.py", "VALUE = 1\n")
        self.write(repo, f"{package}/json.py", "DEAD_STDLIB_SHADOW = 1\n")
        self.write(repo, f"{package}/current/handler.py", "DEAD_SAME_BASENAME = 1\n")
        self.write(repo, f"{package}/dead_subpkg/__init__.py", "from . import dead_leaf\n")
        self.write(repo, f"{package}/dead_subpkg/dead_leaf.py", "DEAD_LEAF = 1\n")
        self.write(repo, f"{package}/cycle_a.py", "from . import cycle_b\n")
        self.write(repo, f"{package}/cycle_b.py", "from . import cycle_a\n")
        errors = self.verify(repo, "harness")
        for dead_name in ("orphan.py", "json.py", "current/handler.py", "dead_subpkg/__init__.py", "dead_subpkg/dead_leaf.py", "cycle_a.py", "cycle_b.py"):
            self.assertTrue(any(dead_name in e and "unreachable" in e for e in errors), (dead_name, errors))

    def test_hatch_alias_main_dunder_and_manifest_launchers_root_modules(self) -> None:
        repo = self.repo("mindie-agent-cc", "0.1.32")
        self.write(
            repo,
            "pyproject.toml",
            '[project]\nname = "mindie-agent-cc"\nversion = "0.1.32"\n'
            '[project.scripts]\nmindie-agent-cc = "mindie_cc.cli:main"\n'
            '[tool.hatch.build.targets.wheel.sources]\nscripts = "mindie_cc"\n',
        )
        self.write(repo, "scripts/__init__.py", "")
        self.write(repo, "scripts/cli.py", "from . import runtime\n\ndef main():\n    return runtime.VALUE\n")
        self.write(repo, "scripts/runtime.py", "VALUE = 1\n")
        self.write(repo, "scripts/__main__.py", "from . import main_entry\n")
        self.write(repo, "scripts/main_entry.py", "VALUE = 2\n")
        self.write(repo, "scripts/plugin_launch.py", "VALUE = 3\n")
        self.write(repo, "scripts/host_bridge.py", "VALUE = 4\n")
        self.write(repo, "plugin.json", json.dumps({"launcher": "scripts/plugin_launch.py"}))
        self.write(repo, "host3.mjs", 'const launcher = "scripts/host_bridge.py";\n')
        self.assertEqual(self.verify(repo, "mindie-agent-cc"), [])

    def test_div_path_chains_and_unique_worker_basenames_reach_modules(self) -> None:
        kimi = self.repo("mindie-agent-kimi", "0.1.33")
        self.write(kimi, "scripts/__init__.py", "")
        self.write(kimi, "scripts/transcript.py", "def identify():\n    return True\n")
        self.write(
            kimi,
            "tests/test_legacy_self_upgrade.py",
            'from pathlib import Path\n\ndef test_shim(repo_root: Path) -> None:\n    assert (repo_root / "scripts" / "transcript.py").is_file()\n',
        )
        self.assertEqual(self.verify(kimi, "mindie-agent-kimi"), [])

        coord = self.repo("coordinator", "0.7.14")
        self.write(
            coord,
            "mindie_coordinator/__init__.py",
            'def load_probe() -> str:\n    return "host_probe_worker.py"\n',
        )
        self.write(coord, "mindie_coordinator/workers/host_probe_worker.py", "PROBE = 1\n")
        self.assertEqual(self.verify(coord, "coordinator"), [])

    def test_real_git_inventory_ignores_untracked_legacy_file(self) -> None:
        from host_compatibility_gate import subprocess_window_kwargs

        win_kw = subprocess_window_kwargs(os_mod=os, subprocess_mod=subprocess)
        repo = self.repo("harness", "0.1.5")
        self.write(repo, "mindie_harness/__init__.py", "")
        subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "init", "-q", str(repo)], timeout=15.0, check=True, **win_kw)
        subprocess.run(["git", "-C", str(repo), "add", "."], timeout=15.0, check=True, **win_kw)
        self.write(repo, "mindie_harness/untracked_legacy.py", "VALUE = 1\n")
        self.assertEqual(self.verify(repo, "harness"), [])
        subprocess.run(["git", "-C", str(repo), "add", "mindie_harness/untracked_legacy.py"], timeout=15.0, check=True, **win_kw)
        errors = self.verify(repo, "harness")
        self.assertTrue(any("untracked_legacy.py" in e for e in errors), errors)

    # --------------------------------------------------------------- Check C/D
    def test_broken_link_anchor_and_inline_gate_path_are_rejected(self) -> None:
        hub = self.hub()
        readme = (hub / "README.md").read_text(encoding="utf-8")
        self.write(
            hub,
            "README.md",
            readme
            + "\n[ok-query](docs/README.md?plain=1#releases)"
            + " · [missing](docs/missing.md)"
            + " · [anchor](#missing-anchor)"
            + " · `.github/scripts/deleted_sub/missing_gate.py`\n",
        )
        errors = gate.verify_code_doc_hygiene([self.root], main_repo=hub)
        self.assertFalse(any("plain=1" in e for e in errors), errors)
        self.assertTrue(any("broken relative link" in e and "docs/missing.md" in e for e in errors), errors)
        self.assertTrue(any("broken internal anchor" in e and "missing-anchor" in e for e in errors), errors)
        self.assertTrue(any("missing_gate.py" in e and "does not exist" in e for e in errors), errors)

    def test_published_release_index_requires_links_but_skips_failed_unpublished(self) -> None:
        hub = self.hub()
        self.write(hub, "docs/README.md", "# Docs\n\n## Releases\n\n[0.1.9](releases/0.1.9.md)\n")
        self.write(hub, "docs/README.en.md", "# Docs\n\n## Releases\n\nNo links yet.\n")
        errors = gate.verify_code_doc_hygiene([self.root], main_repo=hub)
        self.assertTrue(any("docs/README.md does not link published release docs/releases/0.1.0.md" in e for e in errors), errors)
        self.assertTrue(any("must not list failed_unpublished release 0.1.9" in e for e in errors), errors)

    def test_missing_counterpart_and_h2_mismatch_are_rejected(self) -> None:
        repo = self.repo("harness", "0.1.5")
        self.write(repo, "docs/orphan.en.md", "# Orphan\n\n## Only English\n")
        self.write(repo, "docs/pair.md", "# Pair\n\n## One\n\n## Two\n")
        self.write(repo, "docs/pair.en.md", "# Pair\n\n## One\n")
        errors = self.verify(repo, "harness")
        self.assertTrue(any("orphan.en.md" in e and "counterpart" in e for e in errors), errors)
        self.assertTrue(any("H2 section mismatch" in e and "docs/pair.md" in e for e in errors), errors)

    def test_historical_root_docs_custom_anchors_and_root_counterpart_pairing(self) -> None:
        repo = self.repo("remote-dev", "0.11.15")
        self.write(repo, "remote_dev/__init__.py", "")
        self.write(repo, "CHANGELOG.md", "- Deleted `remote_dev/removed_legacy.py` in v0.10.0.\n")
        self.write(repo, "THIRD_PARTY_NOTICES.md", "- Removed `remote_dev/old_notice.py`.\n")
        self.write(repo, "DESIGN.md", "# Design\n\n## Architecture\n")
        self.write(repo, "CLIENT_COMPATIBILITY.md", "# Clients\n\n## Matrix\n")
        self.write(
            repo,
            "docs/design.zh.md",
            "# 设计\n\n## Known limitation: cancel {#custom-cancel-limit}\n\n"
            "See [standard](#known-limitation-cancel) and [custom](#custom-cancel-limit).\n",
        )
        self.write(repo, "docs/client-compatibility.zh.md", "# 兼容性\n\n## 矩阵\n")
        self.assertEqual(self.verify(repo, "remote-dev"), [])

    # ------------------------------------------------------------- Activation
    def test_activation_floors_main_repo_and_required_corpora(self) -> None:
        self.assertEqual(gate.verify_code_doc_hygiene([]), [])
        skipped = self.repo("sim", "0.9.0")
        self.write(skipped, "src/mindie_sim/__init__.py", "")
        self.write(skipped, "src/mindie_sim/widget_legacy.py", "VALUE = 1\n")
        self.assertEqual(gate.verify_code_doc_hygiene([self.root]), [])
        (skipped / "pyproject.toml").write_text('[project]\nname = "mindie-sim"\nversion = "0.9.19"\n', encoding="utf-8")
        errors = gate.verify_code_doc_hygiene([self.root])
        self.assertTrue(any("widget_legacy.py" in e for e in errors), errors)
        (skipped / "pyproject.toml").write_text('[project]\nname = "mindie-sim"\nversion = "0.9.0"\n', encoding="utf-8")

        corpus = self.repo("knowledge-vllm-ascend", None, pyproject=False)
        self.write(corpus, "docs/README.md", "# Corpus\n\n## Units\n")
        self.write(corpus, "docs/README.en.md", "# Corpus\n\n## Units\n")
        self.assertEqual(gate.verify_code_doc_hygiene([self.root], required_repos=["knowledge-vllm-ascend"]), [])

        empty = self.root / "empty"
        empty.mkdir()
        missing = gate.verify_code_doc_hygiene([empty], required_repos=["harness"])
        self.assertTrue(any("harness: sibling checkout not found" in e for e in missing), missing)
        enforced = gate.verify_code_doc_hygiene([empty], main_repo=None, enforce_all=True)
        self.assertTrue(any("--enforce-all requires an explicit main repository" in e for e in enforced), enforced)
        self.assertGreaterEqual(len(enforced), len(gate.CODE_DOC_HYGIENE_FLOOR_VERSIONS) + 1)

    def test_explicit_main_repo_override_is_honoured(self) -> None:
        hub = self.hub()
        custom = self.root / "custom-hub"
        (custom / ".git").mkdir(parents=True)
        self.write(custom, "README.md", "# Custom\n\n## Overview\n")
        errors = gate.verify_code_doc_hygiene(
            [], main_repo=hub, explicit_repos={"mindie-agent": custom}
        )
        self.assertTrue(any("mindie-agent: required bilingual living document" in e for e in errors), errors)
        self.assertFalse(any("docs/releases/0.1.0" in e for e in errors), errors)
        explicit_only = gate.verify_code_doc_hygiene([], explicit_repos={"mindie-agent": custom})
        self.assertTrue(any("required bilingual living document README.en.md" in e for e in explicit_only), explicit_only)
        self.assertTrue(gate.verify_code_doc_hygiene([], required_repos=["mindie-agent"]))

    def test_round2_abi_importers_relative_import_module_and_markdown_edges(self) -> None:
        repo = self.repo("harness", "0.1.5")
        pkg = "mindie_harness"
        self.write(repo, "plugin.json", json.dumps({"args": ["-m", "mindie_harness.json_worker"]}))
        self.write(repo, f"{pkg}/__init__.py", '\ufefffrom importlib import import_module\nimport pathlib\nDEAD = pathlib.Path("retired") / "h1.py"\nDEAD2 = pathlib.Path("retired", "h2.py")\nimport_module(".dyn_mod", __package__)\n')
        self.write(repo, f"{pkg}/dyn_mod.py", "OK = 1\n")
        self.write(repo, f"{pkg}/json_worker.py", "OK = 2\n")
        self.write(repo, f"{pkg}/live/h1.py", "DEAD = 1\n")
        self.write(repo, f"{pkg}/live/h2.py", "DEAD = 2\n")
        self.write(repo, f"{pkg}/neg_main.py", 'if not (__name__ == "__main__"):\n    pass\n')
        self.write(repo, f"{pkg}/u_v1.py", '"""ABI 1.\n\nUpstream-ABI: aclnnOneKernel\n"""\nfrom v import aclnnOneKernel\nif __name__ == "__main__":\n    pass\n')
        self.write(repo, f"{pkg}/u_v2.py", '"""ABI 2.\n\nUpstream-ABI: aclnnTwoKernel\n"""\nfrom v import aclnnTwoKernel\nif __name__ == "__main__":\n    pass\n')
        self.write(repo, "docs/guide.md", "# Guide\n\n## Foo\n\n## Foo\n\n## Foo-1\n\n[ok](/README.md) · [col](#foo-1-1) · [empty]( )\n")
        self.write(repo, "docs/guide.en.md", "# Guide\n\n## Foo\n\n## Foo\n\n## Foo-1\n")
        errors = self.verify(repo, "harness")
        self.assertFalse(any("dyn_mod.py" in e or "json_worker.py" in e or "#foo-1-1" in e or "/README.md" in e for e in errors), errors)
        for expected in ("live/h1.py", "live/h2.py", "neg_main.py", "u_v1.py", "empty link destination"):
            self.assertTrue(any(expected in e for e in errors), (expected, errors))


if __name__ == "__main__":
    unittest.main()
