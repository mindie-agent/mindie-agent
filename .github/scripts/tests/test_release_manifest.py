"""Product publication inputs must exist and name the channel's exact sources."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_auto_update_readiness as gate
from release_doc_hygiene import product_inputs_changed
from sibling_readme_sync import verify_product_benchmark_manifest


class PublicationInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mindie-release-input-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        environment = patch.dict("os.environ", {name: str(self.root / name) for name in (
            "HOME", "USERPROFILE", "MINDIE_CONFIG_HOME", "MINDIE_DATA_HOME", "MINDIE_DIAGNOSTICS_ROOT")})
        environment.start()
        self.addCleanup(environment.stop)
        self.channel = dict(current_patch_version="0.1.10", components={
            "remote-dev": dict(repository="mindie-agent/remote-dev", version="0.11.6", commit="a"*40)})
        self.path = self.root / "docs/releases/0.1.10/benchmark-manifest.json"

    def write(self, rows):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(dict(schema_version="mindie-release-manifest/1",
            product_version="0.1.10", repositories=rows)), encoding="utf-8", newline="\n")

    def test_missing_input_blocks_before_tagging(self):
        self.assertTrue(verify_product_benchmark_manifest(self.channel, self.root))

    def test_matching_published_sources_pass(self):
        self.write([dict(repository="mindie-agent/remote-dev", version="0.11.6", revision="a"*40)])
        self.assertEqual(verify_product_benchmark_manifest(self.channel, self.root), [])

    def test_stale_and_duplicate_sources_block(self):
        row = dict(repository="mindie-agent/remote-dev", version="0.11.5", revision="b"*40)
        self.write([row])
        self.assertTrue(verify_product_benchmark_manifest(self.channel, self.root))
        row.update(version="0.11.6", revision="a"*40)
        self.write([row, row])
        self.assertTrue(verify_product_benchmark_manifest(self.channel, self.root))

    def test_product_inputs_changed_routes_new_r4_and_r7_gate_modules(self):
        repo = self.root / "hub-routing"
        repo.mkdir()
        run_git = lambda *args: subprocess.run(
            ["git", "-c", "core.autocrlf=false", "-c", "user.name=Test", "-c", "user.email=t@example.invalid", *args],
            cwd=repo, capture_output=True, text=True, encoding="utf-8", check=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()
        run_git("init", "-q")
        (repo / ".github/scripts").mkdir(parents=True)
        for script_name in ("iron_rule_ast_gate.py", "functional_smoke_gate.py"):
            (repo / ".github/scripts" / script_name).write_text("# v1\n", encoding="utf-8", newline="\n")
        run_git("add", ".")
        run_git("commit", "-qm", "init")
        head = run_git("rev-parse", "HEAD")
        for script_name in ("iron_rule_ast_gate.py", "functional_smoke_gate.py"):
            base = head
            (repo / ".github/scripts" / script_name).write_text("# v2\n", encoding="utf-8", newline="\n")
            run_git("add", ".")
            run_git("commit", "-qm", f"touch {script_name}")
            head = run_git("rev-parse", "HEAD")
            self.assertTrue(product_inputs_changed(base, repository=repo))

    def test_r3_requires_all_nine_runtime_packages_in_agy_product_contract(self):
        comps = ("harness", "knowledge", "remote-dev", "diagnostics", "debugger", "profiler", "sim", "coordinator", "npu-top")
        dist = {
            "harness": "mindie-harness", "knowledge": "mindie-knowledge", "remote-dev": "remote-dev",
            "diagnostics": "mindie-diagnostics", "debugger": "mindie-debugger", "profiler": "mindie-profiler",
            "sim": "mindie-sim", "coordinator": "mindie-coordinator", "npu-top": "npu-top",
        }
        manifest = {
            "components": {
                c: {"repository": f"mindie-agent/{c}", "version": "0.1.5", "tag": "v0.1.5", "commit": "a" * 40}
                for c in comps
            },
            "corpora": {"knowledge-vllm-ascend": {"commit": "b" * 40}},
        }
        sibs = self.root / "sibs"
        agy = sibs / "mindie-agent-agy"
        (agy / ".git").mkdir(parents=True)
        sources = "".join(f'{dist[c]} = {{git = "https://github.com/mindie-agent/{c}", rev = "{"a" * 40}"}}\n' for c in comps)
        (agy / "pyproject.toml").write_text(
            f'[project]\nname = "mindie-agent-agy"\nversion = "0.1.22"\ndependencies = {json.dumps(list(dist.values()))}\n'
            f'[tool.uv.sources]\n{sources}',
            encoding="utf-8",
            newline="\n",
        )
        # Omitting mindie-debugger in mindie-agent-agy product-contract.json now fails closed!
        (agy / "product-contract.json").write_text(
            json.dumps({
                "publication": {"verified_commit": "b" * 40},
                "components": {pkg: "0.1.5" for c, pkg in dist.items() if pkg != "mindie-debugger"},
            }),
            encoding="utf-8",
            newline="\n",
        )
        errs = gate.verify_components_and_plugins(manifest, [sibs], require_siblings=False)
        self.assertTrue(any("mindie-agent-agy: product-contract.json missing mindie-debugger" in e for e in errs), errs)

        for bad_components in ([], ["x"], None):
            (agy / "product-contract.json").write_text(
                json.dumps({"publication": {"verified_commit": "b" * 40}, "components": bad_components}),
                encoding="utf-8",
                newline="\n",
            )
            bad_errs = gate.verify_components_and_plugins(manifest, [sibs], require_siblings=False)
            self.assertTrue(any("`components` must be a JSON object" in e for e in bad_errs), bad_errs)

        (agy / "product-contract.json").write_text(
            json.dumps({
                "publication": {"verified_commit": "b" * 40},
                "components": {pkg: "0.1.5" for pkg in dist.values()},
            }),
            encoding="utf-8",
            newline="\n",
        )
        self.assertEqual(gate.verify_components_and_plugins(manifest, [sibs], require_siblings=False), [])


if __name__ == "__main__":
    unittest.main()
