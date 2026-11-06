"""Product publication inputs must exist and name the channel's exact sources."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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


if __name__ == "__main__":
    unittest.main()
