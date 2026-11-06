"""R6 keeps independent release documentation separate from product snapshots."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import check_auto_update_readiness as gate
from release_doc_hygiene import product_inputs_changed, verify_release_doc_hygiene
from sibling_readme_sync import PRODUCT_DOC_PATHS, sync_docs_versions, sync_sibling_readmes


class ReleaseDocScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.TemporaryDirectory(prefix="mindie-r6-fixtures-")
        cls.addClassCleanup(cls.base.cleanup)
        root = Path(cls.base.name)
        environment = patch.dict(os.environ, {name: str(root / name) for name in (
            "HOME", "USERPROFILE", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME",
            "MINDIE_CONFIG_HOME", "MINDIE_DATA_HOME", "MINDIE_DIAGNOSTICS_ROOT",
            "MINDIE_DIAGNOSTICS_CONFIG")})
        environment.start()
        cls.addClassCleanup(environment.stop)
        cls.template = root / "git-template"
        cls.template.mkdir()
        gate._run_cmd(["git", "init", "-q", str(cls.template)]).check_returncode()
        (cls.template / ".gitattributes").write_text("* text=auto eol=lf\n", newline="\n")
        (cls.template / ".editorconfig").write_text("root = true\n[*]\nend_of_line = lf\n", newline="\n")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=self.base.name)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.main = self.root / "mindie-agent"
        self.main.mkdir()
        self.manifest = json.loads((SCRIPTS.parents[1] / "channels/0.1.json").read_text(encoding="utf-8"))
        self.manifest["components"]["knowledge"]["version"] = "0.13.14"
        self.manifest["components"]["diagnostics"]["version"] = "0.5.8"
        (self.main / "channels").mkdir()
        self.channel = self.main / "channels/0.1.json"
        self.channel.write_text(json.dumps(self.manifest), newline="\n")
        (self.main / "README.md").write_text("Historical product combination\n", newline="\n")
        self.knowledge = self.repo("knowledge", "0.13.15")
        self.diagnostics = self.repo("diagnostics", "0.5.9")
        # An unrelated repository's stale README must not block knowledge.
        self.readmes(self.diagnostics, "diagnostics", "0.5.7")

    def repo(self, name, version):
        repo = self.root / name
        shutil.copytree(self.template, repo)
        (repo / "pyproject.toml").write_text(
            f'[project]\nname = "mindie-{name}"\nversion = "{version}"\n', newline="\n")
        self.readmes(repo, name, version)
        return repo

    def readmes(self, repo, name, version, *, wheel=None, paired="0.1.11"):
        text = (f'![Release](https://img.shields.io/badge/Release-v{version}-blue)\n'
                f'paired with `mindie-agent {paired}`\n'
                f'https://github.com/mindie-agent/{name}/releases/download/v{wheel or version}/'
                f'mindie_{name}-{wheel or version}-py3-none-any.whl\n')
        for filename in ("README.md", "README.en.md"):
            (repo / filename).write_text(text, encoding="utf-8", newline="\n")

    def check(self, *names, scope="independent", run=None):
        return verify_release_doc_hygiene(
            self.main, self.manifest, [self.root], scope=scope, release_repos=list(names),
            require_siblings=False, run=run or gate._run_cmd)

    def unchanged_inputs(self):
        return {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

    def test_new_component_version_does_not_require_updating_product_or_peers(self):
        before = self.unchanged_inputs()
        self.assertEqual(self.check("knowledge"), [])
        self.assertEqual(self.unchanged_inputs(), before)
        self.assertEqual(self.manifest["components"]["knowledge"]["version"], "0.13.14")

    def test_independent_release_still_rejects_its_own_badge_and_wheel_drift(self):
        self.readmes(self.knowledge, "knowledge", "0.13.14")
        self.assertTrue(self.check("knowledge"))
        self.readmes(self.knowledge, "knowledge", "0.13.15", wheel="0.13.14")
        self.assertTrue(self.check("knowledge"))
        self.readmes(self.knowledge, "knowledge", "0.13.15")
        self.assertEqual(self.check("knowledge"), [])

    def test_selected_component_checks_optional_docs_and_lf(self):
        docs = self.knowledge / "docs"
        docs.mkdir()
        (docs / "README.md").write_text(
            "https://github.com/mindie-agent/knowledge/releases/download/v0.13.14/"
            "mindie_knowledge-0.13.14-py3-none-any.whl\n", newline="\n")
        self.assertTrue(self.check("knowledge"))
        (docs / "README.md").unlink()
        (self.knowledge / "source.py").write_bytes(b"print('fixture')\r\n")
        self.assertTrue(self.check("knowledge"))
        (self.knowledge / "source.py").write_bytes(b"print('fixture')\n")
        self.assertEqual(self.check("knowledge"), [])

    def test_source_manifest_errors_never_fall_back_to_channel_version(self):
        (self.knowledge / "pyproject.toml").unlink()
        self.assertTrue(self.check("knowledge"))
        (self.knowledge / "kimi.plugin.json").write_text('{"version":"0.13.15"}\n', newline="\n")
        self.assertTrue(self.check("knowledge"))

    def test_native_plugin_uses_its_manifests_and_rejects_conflicting_versions(self):
        plugin = self.repo("mindie-agent-kimi", "0.1.18")
        (plugin / "pyproject.toml").unlink()
        (plugin / "kimi.plugin.json").write_text('{"version":"0.1.18"}\n', newline="\n")
        self.assertEqual(self.check("mindie-agent-kimi"), [])
        (plugin / "pyproject.toml").write_text('[project]\nversion="0.1.17"\n', newline="\n")
        self.assertTrue(self.check("mindie-agent-kimi"))

    def test_native_plugin_rejects_stale_self_release_statements(self):
        plugin = self.repo("mindie-agent-dsh", "0.1.17")
        (plugin / "pyproject.toml").unlink()
        (plugin / "package.json").write_text('{"version":"0.1.17"}\n', newline="\n")
        for statement in ("当前正式版本为 `0.1.16`", "latest `v0.1.16` release"):
            with self.subTest(statement=statement):
                self.readmes(plugin, plugin.name, "0.1.17")
                readme = plugin / "README.md"
                original = readme.read_text(encoding="utf-8")
                readme.write_text(original + statement + "\n", encoding="utf-8", newline="\n")
                self.assertTrue(self.check(plugin.name))
                readme.write_text(original + statement.replace("0.1.16", "0.1.17") + "\n",
                                  encoding="utf-8", newline="\n")
                self.assertEqual(self.check(plugin.name), [])

    def test_own_release_links_and_alt_text_do_not_expand_to_peer_versions(self):
        readme = self.knowledge / "README.md"
        original = readme.read_text(encoding="utf-8")
        peers = ("https://github.com/mindie-agent/diagnostics/releases/tag/v0.5.7\n"
                 "https://github.com/mindie-agent/diagnostics/releases/download/v0.5.7/"
                 "mindie_diagnostics-0.5.7-py3-none-any.whl\n")
        for declaration in (
            "https://github.com/mindie-agent/knowledge/releases/tag/v0.13.14",
            '<img alt="Release v0.13.14" src="release.svg">',
        ):
            with self.subTest(declaration=declaration):
                readme.write_text(original + peers + declaration + "\n", newline="\n")
                self.assertTrue(self.check("knowledge"))
                readme.write_text(original + peers + declaration.replace("0.13.14", "0.13.15") + "\n",
                                  newline="\n")
                self.assertEqual(self.check("knowledge"), [])

    def test_nested_relative_sibling_root_checks_the_selected_repository(self):
        nested = self.root / "nested" / "siblings"
        nested.mkdir(parents=True)
        shutil.copytree(self.knowledge, nested / "knowledge")
        def check(roots):
            return verify_release_doc_hygiene(
                self.main, self.manifest, roots, scope="independent", release_repos=["knowledge"],
                require_siblings=False, run=gate._run_cmd)
        with contextlib.chdir(self.root):
            self.assertEqual(check([nested]), [])
            self.assertEqual(check([Path("nested/siblings")]), [])
            (nested / "knowledge" / "source.py").write_bytes(b"print('fixture')\r\n")
            self.assertTrue(check([Path("nested/siblings")]))

    def test_multiple_selected_repositories_validate_their_own_versions(self):
        self.assertTrue(self.check("knowledge", "diagnostics"))
        self.readmes(self.diagnostics, "diagnostics", "0.5.9")
        self.assertEqual(self.check("knowledge", "diagnostics"), [])

    def test_corpus_release_does_not_invent_a_package_version(self):
        corpus = self.root / "knowledge-infer-core"
        shutil.copytree(self.template, corpus)
        (corpus / "README.md").write_text("Corpus uses per-unit revisions.\n", newline="\n")
        self.assertEqual(self.check("knowledge-infer-core"), [])

    def test_missing_selected_checkout_cannot_be_implicitly_skipped(self):
        shutil.rmtree(self.knowledge)
        self.assertTrue(self.check("knowledge"))

    def test_source_read_timeout_stays_a_timeout(self):
        read = Path.read_text
        def timed(path, *args, **kwargs):
            if path.resolve() == (self.knowledge / "pyproject.toml").resolve():
                raise TimeoutError("fixture read deadline")
            return read(path, *args, **kwargs)
        with patch.object(Path, "read_text", timed), self.assertRaises(TimeoutError):
            self.check("knowledge")

    def test_product_scope_keeps_full_combination_alignment(self):
        before = self.unchanged_inputs()
        # The external product-document command is a separate boundary. The
        # real cross-repository validator below must still reject both drifts.
        def product_commands(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, "", "")
        errors = self.check(scope="product", run=product_commands)
        self.assertTrue(any("knowledge/README" in error for error in errors))
        self.assertTrue(any("diagnostics/README" in error for error in errors))
        self.assertEqual(self.unchanged_inputs(), before)
        paired = self.manifest["current_patch_version"]
        self.readmes(self.knowledge, "knowledge", "0.13.14", paired=paired)
        self.assertTrue(self.check(scope="product", run=product_commands))
        self.readmes(self.diagnostics, "diagnostics", "0.5.8", paired=paired)
        self.assertEqual(self.check(scope="product", run=product_commands), [])
        self.assertEqual(sync_sibling_readmes(
            self.main, self.manifest, False, siblings_roots=[self.root]), [])

    def commit_product_fixture(self):
        gate._run_cmd(["git", "add", "--all"], cwd=self.main).check_returncode()
        gate._run_cmd(["git", "-c", "user.name=R6 Fixture", "-c", "user.email=r6@example.invalid",
                       "commit", "--no-verify", "-q", "-m", "fixture"], cwd=self.main).check_returncode()
        return gate._run_cmd(["git", "rev-parse", "HEAD"], cwd=self.main).stdout.strip()

    def test_ci_routes_all_product_documents_and_rejects_real_version_drift(self):
        shutil.copytree(self.template, self.main, dirs_exist_ok=True)
        for relative in PRODUCT_DOC_PATHS:
            path = self.main / relative
            path.parent.mkdir(exist_ok=True)
            path.write_text("Product fixture\n", newline="\n")
        migration = self.main / "docs/simulation-consumer-migration.md"
        version = self.manifest["components"]["mindie-agent-codex"]["version"]
        migration.write_text(f"| **`mindie-agent-codex`** | `v{version}` |\n", newline="\n")
        self.assertEqual(sync_docs_versions(self.main, self.manifest, False), [])
        base = self.commit_product_fixture()
        architecture = self.main / "docs/architecture.md"
        architecture.write_text("An independent documentation change\n", newline="\n")
        self.commit_product_fixture()
        self.assertFalse(product_inputs_changed(base, repository=self.main))

        migration.write_text("| **`mindie-agent-codex`** | `v0.0.0` |\n", newline="\n")
        head = self.commit_product_fixture()
        self.assertTrue(product_inputs_changed(base, repository=self.main))
        self.assertTrue(any("simulation-consumer-migration.md" in error
                            for error in sync_docs_versions(self.main, self.manifest, False)))

        # Every document owned by the sync and the gate implementation must
        # route through product checks even when it is the only changed input.
        for relative in (*PRODUCT_DOC_PATHS, ".github/scripts/release_doc_hygiene.py",
                         ".github/workflows/pr-checklist.yml"):
            with self.subTest(relative=relative):
                base = head
                path = self.main / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write("Changed product input\n")
                head = self.commit_product_fixture()
                self.assertTrue(product_inputs_changed(base, repository=self.main))

    def test_ci_routing_propagates_git_failure(self):
        shutil.copytree(self.template, self.main, dirs_exist_ok=True)
        self.commit_product_fixture()
        with self.assertRaises(subprocess.CalledProcessError):
            product_inputs_changed("missing-base-ref", repository=self.main)

    def test_global_write_tools_require_explicit_product_intent_before_any_write(self):
        before = self.unchanged_inputs()
        for filename in ("sync_org_versions.py", "sibling_readme_sync.py"):
            for operation in ("--check", "--write"):
                with self.subTest(tool=filename, operation=operation):
                    result = gate._run_cmd([sys.executable, str(SCRIPTS / filename), operation], cwd=self.main)
                    self.assertEqual(result.returncode, 2)
        self.assertEqual(self.unchanged_inputs(), before)

    def test_gate_default_requires_independent_target_instead_of_global_sync(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            gate.main([])
        self.assertEqual(caught.exception.code, 2)

    def test_cli_default_routes_selected_release_through_real_independent_r6(self):
        # Other checklist domains have their own integration checks. This
        # exercises CLI routing and the real Git/LF/README boundary for R6.
        with contextlib.ExitStack() as stack:
            for name in ("verify_channel_schema", "verify_corpora", "verify_components_and_plugins",
                         "verify_flexible_component_compatibility"):
                stack.enter_context(patch.object(gate, name, return_value=[]))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            args = ["--channel", str(self.channel), "--siblings-root", str(self.root),
                    "--release-repo", "knowledge"]
            before = self.unchanged_inputs()
            self.assertEqual(gate.main(args), 0)
            self.assertEqual(self.unchanged_inputs(), before)
            self.readmes(self.knowledge, "knowledge", "0.13.14")
            self.assertEqual(gate.main(args), 1)


if __name__ == "__main__":
    unittest.main()
