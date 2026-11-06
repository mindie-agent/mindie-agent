"""Published dependency advances do not rewrite historical product combinations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_auto_update_readiness as gate
import release_tag_integrity
import sibling_readme_sync


class IndependentPluginPinsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mindie-plugin-pins-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        environment = patch.dict(os.environ, {key: str(self.root / key) for key in (
            'HOME', 'USERPROFILE', 'MINDIE_CONFIG_HOME', 'MINDIE_DATA_HOME',
            'MINDIE_DIAGNOSTICS_ROOT', 'MINDIE_DIAGNOSTICS_CONFIG')})
        environment.start()
        self.addCleanup(environment.stop)
        self.repo = self.root / 'remote-dev'
        self.repo.mkdir()
        self.git('init', '-q')
        self.old = self.commit('0.11.6')
        self.git('tag', 'v0.11.6')
        self.new = self.commit('0.11.7')
        self.git('tag', '-a', 'v0.11.7', '-m', 'release')
        names = ('knowledge', 'remote-dev', 'diagnostics', 'debugger', 'profiler', 'sim', 'coordinator')
        self.manifest = dict(components={name: dict(repository=f'mindie-agent/{name}',
            version='0.11.6' if name == 'remote-dev' else '1.0.0',
            tag='v0.11.6' if name == 'remote-dev' else 'v1.0.0',
            commit=self.old if name == 'remote-dev' else 'a' * 40) for name in names},
            corpora={'knowledge-vllm-ascend': {'commit': 'a' * 40}})
        self.plugin = self.root / 'mindie-agent-codex/plugins/mindie-agent'
        self.plugin.mkdir(parents=True)
        gate._run_cmd(['git', 'init', '-q', str(self.plugin.parents[1])]).check_returncode()
        self.pin(self.new)

    def git(self, *args):
        return subprocess.run(['git', '-c', 'user.name=Release Test',
            '-c', 'user.email=release@example.invalid', *args], cwd=self.repo,
            capture_output=True, text=True, check=True, timeout=5,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout.strip()

    def commit(self, version):
        (self.repo / 'pyproject.toml').write_text(
            f'[project]\nname = "remote-dev"\nversion = "{version}"\n', newline='\n')
        self.git('add', '.')
        self.git('commit', '-qm', version)
        return self.git('rev-parse', 'HEAD')

    def pin(self, revision):
        dist = {'knowledge': 'mindie-knowledge', 'remote-dev': 'remote-dev',
                'diagnostics': 'mindie-diagnostics', 'debugger': 'mindie-debugger',
                'profiler': 'mindie-profiler', 'sim': 'mindie-sim', 'coordinator': 'mindie-coordinator'}
        sources = {name: (revision if name == 'remote-dev' else 'a' * 40) for name in dist}
        project = ('[project]\nname = "mindie-agent-codex"\nversion = "0.1.22"\n'
                   'dependencies = ' + json.dumps(list(dist.values())) + '\n[tool.uv.sources]\n')
        project += ''.join(f'{dist[name]} = {{git = "https://github.com/mindie-agent/{name}", '
                           f'rev = "{sha}"}}\n' for name, sha in sources.items())
        (self.plugin / 'pyproject.toml').write_text(project, newline='\n')
        lock = ('[[package]]\nname = "mindie-agent-codex"\ndependencies = [' +
                ','.join('{name = "' + name + '"}' for name in dist.values()) + ']\n')
        lock += ''.join(f'[[package]]\nname = "{dist[name]}"\nsource = {{git = '
                        f'"https://github.com/mindie-agent/{name}?rev={sha}#{sha}"}}\n'
                        for name, sha in sources.items())
        (self.plugin / 'uv.lock').write_text(lock, newline='\n')
        (self.plugin / 'product-contract.json').write_text(json.dumps({
            'publication': {'verified_commit': 'a' * 40}}), newline='\n')

    def check(self, **kwargs):
        return gate.verify_components_and_plugins(self.manifest, [self.root],
                                                  require_siblings=False, **kwargs)

    def test_independent_formal_advance_passes_without_changing_inputs(self):
        before = (json.dumps(self.manifest), (self.plugin / 'pyproject.toml').read_bytes())
        self.assertEqual(self.check(independent=True), [])
        self.assertEqual(before, (json.dumps(self.manifest), (self.plugin / 'pyproject.toml').read_bytes()))

    def test_product_and_explicit_lockstep_keep_their_combination_boundary(self):
        self.assertTrue(any('ahead of channel' in error for error in self.check()))
        self.assertTrue(any('lockstep' in error for error in self.check(independent=True, strict_lockstep=True)))

    def test_independent_unreleased_commit_is_rejected(self):
        self.pin(self.commit('0.11.8'))
        self.assertTrue(any('not a formal release tag' in error for error in self.check(independent=True)))

    def test_formal_remote_release_failure_remains_blocking(self):
        with patch.object(gate, 'verify_github_releases', return_value=['formal release missing']) as verify:
            self.assertEqual(self.check(independent=True, verify_formal_releases=True), ['formal release missing'])
        dependencies = verify.call_args.args[0]['components']
        self.assertEqual(list(dependencies.values()), [dict(repository='mindie-agent/remote-dev',
                                                          version='0.11.7', commit=self.new)])
        self.assertTrue(verify.call_args.kwargs['verify_commits'])

    def test_remote_tag_commit_must_match_the_actual_pin(self):
        annotated = self.git('rev-parse', 'v0.11.7')
        release = dict(tagName='v0.11.7', isDraft=False, isPrerelease=False,
                       assets=[{'name': 'SHA256SUMS'}])
        manifest = {'components': {'remote-dev': dict(repository='mindie-agent/remote-dev',
                     version='0.11.7', commit=self.new)}}
        for kind, remote in (('commit', self.new), ('tag', self.new), ('tag', self.old)):
            with self.subTest(kind=kind, remote=remote):
                def response(argv, **kwargs):
                    if argv[1] == 'release':
                        value = release
                    elif '/git/ref/tags/' in argv[-1]:
                        value = {'object': {'type': kind, 'sha': annotated if kind == 'tag' else remote}}
                    else:
                        self.assertTrue(argv[-1].endswith('/git/tags/' + annotated))
                        value = {'object': {'type': 'commit', 'sha': remote}}
                    return subprocess.CompletedProcess(argv, 0, json.dumps(value), '')
                with patch.object(sibling_readme_sync.shutil, 'which', return_value='gh'), \
                     patch.object(release_tag_integrity.subprocess, 'run', side_effect=response):
                    errors = sibling_readme_sync.verify_github_releases(manifest, verify_commits=True)
                self.assertEqual(bool(errors), remote != self.new)
                if errors:
                    self.assertIn('expected pinned source ' + self.new, errors[0])


if __name__ == '__main__':
    unittest.main()
