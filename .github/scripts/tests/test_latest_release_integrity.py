"""Replay the incident's public heads through the real installed consumer."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mindie_knowledge.component_releases import Catalog
import check_auto_update_readiness as gate
from release_latest_integrity import verify_latest_components

CAPTURES = Path(__file__).with_name("fixtures") / "latest-release"


class CapturedCatalog(Catalog):
    def read(self, path, *, force=False):
        if path.endswith("/releases/latest"):
            repository = path.split("/")[3]
            tag = {"sim": "0.9.9", "profiler": "0.5.10", "knowledge": "0.13.2"}[repository]
            filename = f"{repository}-v{tag}.json"
        elif "/git/ref/" in path:
            filename = "ref.json"
        elif "/git/tags/" in path:
            filename = "tag.json"
        elif "/contents/" in path:
            filename = "source.json"
        else:
            raise AssertionError(f"unexpected transport read: {path}")
        return json.loads((CAPTURES / filename).read_bytes())

    def asset(self, name, tag, filename):
        return (CAPTURES / filename).read_bytes()


class LatestReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mindie-latest-integrity-")
        self.addCleanup(temporary.cleanup)
        sandbox = patch.dict(os.environ, {name: str(Path(temporary.name) / name) for name in (
            "HOME", "USERPROFILE", "MINDIE_CONFIG_HOME", "MINDIE_DATA_HOME",
            "MINDIE_DIAGNOSTICS_ROOT")})
        sandbox.start()
        self.addCleanup(sandbox.stop)

    def test_complete_published_head_passes_real_consumer(self):
        self.assertEqual(verify_latest_components(
            CapturedCatalog(), names=("mindie-knowledge",)), [])

    def test_incomplete_latest_blocks_even_when_historical_sources_are_complete(self):
        errors = verify_latest_components(CapturedCatalog(), names=(
            "mindie-knowledge", "mindie-sim", "mindie-profiler"))
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("mindie-agent/sim" in error for error in errors))
        self.assertTrue(any("mindie-agent/profiler" in error for error in errors))

    def test_release_cli_rejects_bad_current_heads_after_historical_gates_pass(self):
        def current_heads():
            return verify_latest_components(CapturedCatalog(), names=(
                "mindie-knowledge", "mindie-sim", "mindie-profiler"))

        with contextlib.ExitStack() as stack:
            for name in ("verify_channel_schema", "verify_corpora",
                         "verify_components_and_plugins", "verify_github_releases",
                         "verify_flexible_component_compatibility", "verify_release_doc_hygiene"):
                stack.enter_context(patch.object(gate, name, return_value=[]))
            stack.enter_context(patch.object(gate, "_ensure_knowledge_importable", return_value=True))
            stack.enter_context(patch.object(gate, "verify_current_release_heads",
                                            side_effect=current_heads))
            output, errors = io.StringIO(), io.StringIO()
            stack.enter_context(contextlib.redirect_stdout(output))
            stack.enter_context(contextlib.redirect_stderr(errors))
            self.assertEqual(gate.main(["--release-repo", "knowledge",
                                        "--verify-github-releases"]), 1)
        self.assertIn("mindie-agent/sim", errors.getvalue())
        self.assertIn("mindie-agent/profiler", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
