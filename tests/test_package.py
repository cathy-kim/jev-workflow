"""Portable package acceptance tests. No provider calls or credentials."""
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins' / 'jev'
SKILL = PLUGIN / 'skills' / 'jev-decisions'
SCRIPT = SKILL / 'scripts' / 'decision_kit.py'
PUBLIC_URL = 'https://github.com/cathy-kim/jev-workflow'


def package_files():
    paths = []
    for scope in ('plugins', '.claude-plugin', 'tests', 'examples'):
        paths.extend(p for p in (ROOT / scope).rglob('*') if p.is_file())
    paths.extend(ROOT / p for p in ('docs/installation.md', 'LICENSE', 'SECURITY.md'))
    return paths


class PackageTests(unittest.TestCase):
    def test_manifest(self):
        manifest = json.loads((PLUGIN / '.claude-plugin/plugin.json').read_text())
        self.assertEqual(manifest['name'], 'jev')
        self.assertEqual(manifest['version'], '1.2.0')
        self.assertEqual(manifest['repository'], PUBLIC_URL)
        self.assertEqual(manifest['author'], {'name': 'cathy-kim'})
        self.assertEqual(manifest['license'], 'MIT')
        self.assertFalse(set(manifest) & {'hooks', 'mcpServers', 'lspServers', 'commands'})

    def test_marketplace(self):
        marketplace = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
        self.assertEqual(marketplace['name'], 'jev-workflow')
        self.assertEqual(marketplace['owner'], {'name': 'cathy-kim'})
        self.assertEqual(len(marketplace['plugins']), 1)
        entry = marketplace['plugins'][0]
        self.assertEqual(entry['name'], 'jev')
        self.assertEqual(entry['source'], './plugins/jev')
        self.assertEqual(entry['version'], '1.2.0')
        self.assertEqual(entry['repository'], PUBLIC_URL)

    def test_one_canonical_skill(self):
        self.assertEqual(list((ROOT / 'plugins').rglob('SKILL.md')), [SKILL / 'SKILL.md'])
        content = (SKILL / 'SKILL.md').read_text()
        self.assertTrue(content.startswith('---\nname: jev-decisions\n'))
        for heading in ('Design', 'Implement', 'Test', 'Evaluate', 'Adopt'):
            self.assertIn(heading, content)
        self.assertNotIn('related_skills:', content)

    def test_relative_markdown_links(self):
        for path in package_files():
            if path.suffix != '.md':
                continue
            for target in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', path.read_text()):
                if re.match(r'[a-z]+:', target) or target.startswith('#'):
                    continue
                resolved = (path.parent / target.split('#')[0]).resolve()
                with self.subTest(file=path.relative_to(ROOT), target=target):
                    self.assertTrue(resolved.is_relative_to(ROOT))
                    self.assertTrue(resolved.exists())

    def test_zero_prohibited_files(self):
        # Keep the distributed plugin declarative and self-contained.
        allowed_suffixes = {'.md', '.py', '.json'}
        prohibited_parts = {'.git', 'node_modules', '__pycache__', 'hooks', 'commands', 'dist', 'build'}
        for path in package_files():
            relative = path.relative_to(ROOT)
            with self.subTest(path=str(relative)):
                self.assertFalse(path.is_symlink())
                self.assertFalse(set(relative.parts) & prohibited_parts)
                self.assertFalse(path.name.startswith('.env'))
                self.assertNotIn(path.name, {'.mcp.json', '.npmrc', 'settings.json', 'credentials.json'})
                if path.name != 'LICENSE':
                    self.assertIn(path.suffix, allowed_suffixes)

    def test_plugin_exact_inventory(self):
        expected = {'.claude-plugin/plugin.json'}
        prefix = 'skills/jev-decisions/'
        expected.update(prefix + name for name in (
            'SKILL.md',
            'references/implementation-playbook.md', 'references/typesafe-contract.md',
            'references/providers-evaluation.md', 'references/offline-starter.md',
            'references/research-models.md', 'references/research-sources.json',
            'references/videojev.md', 'references/mjev-spatial.md', 'references/jeva.md',
            'scripts/research_kit.py',
            'scripts/jev_cli.py', 'references/live-client.md',
            'scripts/jev_workflow/__init__.py', 'scripts/jev_workflow/capabilities.py',
            'scripts/jev_workflow/cli.py', 'scripts/jev_workflow/client.py',
            'scripts/jev_workflow/credentials.py', 'scripts/jev_workflow/errors.py',
            'scripts/jev_workflow/installer.py', 'scripts/jev_workflow/mcp_server.py',
            'scripts/jev_workflow/model.py', 'scripts/jev_workflow/providers.py',
            'scripts/jev_workflow/transport.py',
            'scripts/examples/providers/request.synthetic.json',
            'scripts/examples/providers/openai.response.synthetic.json',
            'scripts/examples/providers/typesafe.response.synthetic.json',
            'scripts/examples/providers/openrouter-decisions.response.synthetic.json',
            'scripts/examples/providers/openrouter-structured.response.synthetic.json',
            'templates/design-brief.md', 'templates/evaluation-record.json',
            'templates/question-registry.json', 'scripts/decision_kit.py',
            'scripts/test_decision_kit.py', 'scripts/examples/design.md',
            'scripts/examples/policy.json', 'scripts/examples/policy.synthetic-high-impact.json',
            'scripts/examples/policy.synthetic-recommend.json', 'scripts/examples/request.json',
            'scripts/examples/response.malformed.synthetic.json',
            'scripts/examples/response.synthetic.json', 'scripts/examples/rubric.json'))
        actual = {p.relative_to(PLUGIN).as_posix() for p in PLUGIN.rglob('*') if p.is_file()}
        self.assertEqual(actual, expected)
        for path in PLUGIN.rglob('*'):
            self.assertFalse(path.is_symlink())
            self.assertNotIn(path.name, {'hooks', 'commands', 'node_modules', '__pycache__'})

    def test_all_cli_modes_under_offline_audit_guard(self):
        probe = (
            "import sys, runpy\n"
            "def guard(event, args):\n"
            "    if event.startswith(('socket.', 'urllib.', 'http.client.', 'subprocess.')) or event in "
            "('os.system', 'os.posix_spawn', 'os.spawn', 'os.exec'):\n"
            "        raise RuntimeError('FORBIDDEN_EXTERNAL_ACTION')\n"
            "    if event == 'open' and isinstance(args[0], str):\n"
            "        parts = args[0].replace(chr(92), '/').split('/')\n"
            "        if any(p.startswith('.env') or p in ('.ssh', '.aws', '.config') for p in parts):\n"
            "            raise RuntimeError('FORBIDDEN_SECRET_LOOKUP')\n"
            "sys.addaudithook(guard)\n"
            "sys.argv = sys.argv[1:]\n"
            "runpy.run_path(sys.argv[0], run_name='__main__')\n"
        )
        with tempfile.TemporaryDirectory(prefix='jev-guard-') as directory:
            out = Path(directory).resolve() / 'generated'
            args = ['--request', out / 'request.json', '--response', out / 'response.synthetic.json']
            for command, expected in ((['init', '--out', out], 0),
                                      (['validate', *args], 0),
                                      (['gate', *args, '--policy', out / 'policy.json'], 3)):
                result = subprocess.run([sys.executable, '-B', '-c', probe, str(SCRIPT),
                                         *map(str, command)], capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertEqual(result.stderr, '')
                self.assertIsInstance(json.loads(result.stdout), dict)

    def test_no_machine_paths_or_private_provenance(self):
        # Construct sensitive marker families instead of distributing actual identities.
        patterns = [r'/(?:Users|home)/[A-Za-z0-9_.-]+/', r'[A-Z]:\\Users\\',
                    r'-----BEGIN [A-Z ]*PRIVATE KEY-----']
        catalog_path = SKILL / 'references/research-sources.json'
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        public_revisions = {
            SKILL / 'references' / item['reference']: {a['revision'] for a in item['public_artifacts']}
            for item in catalog['models']
        }
        public_revisions[catalog_path] = set().union(*public_revisions.values())
        public_revisions[SKILL / 'scripts/research_kit.py'] = {item['code_revision'] for item in catalog['models']}
        for path in package_files():
            content = path.read_text(encoding='utf-8')
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertFalse(set(re.findall(r'\b[0-9a-f]{40}\b', content)) - public_revisions.get(path, set()))
            for pattern in patterns:
                with self.subTest(path=str(path.relative_to(ROOT)), pattern=pattern):
                    self.assertIsNone(re.search(pattern, content))

    def test_offline_import_surface(self):
        tree = ast.parse(SCRIPT.read_text())
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                modules.add(node.module)
        self.assertEqual(modules, {'argparse', 'json', 'math', 'pathlib', 're'})

    def test_installation_entrypoints(self):
        text = (ROOT / 'docs/installation.md').read_text()
        for command in ('/plugin marketplace add cathy-kim/jev-workflow',
                        '/plugin install jev@jev-workflow', '/jev:jev-decisions',
                        'claude --plugin-dir ./plugins/jev'):
            self.assertIn(command, text)

    def test_license_and_non_affiliation(self):
        self.assertIn('Copyright (c) 2026 cathy-kim', (ROOT / 'LICENSE').read_text())
        self.assertIn('not affiliated', (ROOT / 'SECURITY.md').read_text())

    def test_demo_real_subprocess(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'examples/offline_demo.py')],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['shadow']['exit_code'], 3)
        self.assertEqual(report['shadow']['output']['decision'], 'REVIEW')
        self.assertEqual(report['recommend']['exit_code'], 0)
        self.assertEqual(report['high_impact']['exit_code'], 2)
        self.assertEqual(report['malformed']['exit_code'], 2)

    def test_runtime_neutral_relocated_skill(self):
        # TMPDIR may be set by the caller to a trusted scratch location.
        with tempfile.TemporaryDirectory(prefix='jev-portability-') as directory:
            root = Path(directory).resolve()
            moved = root / 'any-runtime' / 'skills' / 'jev-decisions'
            shutil.copytree(SKILL, moved)
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover',
                                     '-s', str(moved / 'scripts'), '-p', 'test_decision_kit.py'],
                                    cwd=root, env=env, text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Ran 84 tests', result.stderr)


if __name__ == '__main__':
    unittest.main()
