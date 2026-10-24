"""Installer tests in temporary directories only; never touches a real home or runtime config."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from client_fixtures import SCRIPTS, SKILL
from jev_workflow import installer
from jev_workflow.errors import UsageError

CLI = SCRIPTS / 'jev_cli.py'


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jev-install-')
        self.home = Path(self.tmp.name).resolve()
        self.target = self.home / '.agents' / 'skills'

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_writes_nothing(self):
        plan = installer.install('codex', self.target, dry_run=True)
        self.assertEqual(plan['action'], 'install')
        self.assertTrue(plan['dry_run'])
        self.assertFalse(self.target.exists())
        self.assertIn('SKILL.md', plan['files'])

    def test_install_is_complete_and_idempotent(self):
        result = installer.install('codex', self.target)
        dest = self.target / 'jev-decisions'
        self.assertEqual(result['destination_relative_to_target'], 'jev-decisions')
        self.assertTrue((dest / 'SKILL.md').is_file())
        self.assertTrue((dest / 'scripts' / 'jev_workflow' / 'client.py').is_file())
        self.assertFalse(list(dest.rglob('__pycache__')))
        manifest = json.loads((dest / installer.MANIFEST).read_text())
        self.assertEqual(manifest['runtime'], 'codex')
        self.assertEqual(set(manifest['files']), set(installer.source_files()))
        self.assertEqual(result['invocation'], '$jev-decisions')
        self.assertIn('codex mcp add', result['mcp_registration_example'])
        again = installer.install('codex', self.target)
        self.assertEqual(again['action'], 'already_installed')

    def test_installed_copy_runs_from_its_own_directory(self):
        installer.install('hermes', self.target)
        launcher = self.target / 'jev-decisions' / 'scripts' / 'jev_cli.py'
        result = subprocess.run([sys.executable, '-B', str(launcher), 'providers', '--compact'], cwd=self.home,
                                capture_output=True, text=True, timeout=20,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('openai', json.loads(result.stdout)['providers'])

    def test_collision_refused_then_backup_and_rollback(self):
        dest = self.target / 'jev-decisions'
        dest.mkdir(parents=True)
        (dest / 'SKILL.md').write_text('user customized skill')
        with self.assertRaises(UsageError):
            installer.install('claude', self.target)
        self.assertEqual((dest / 'SKILL.md').read_text(), 'user customized skill')
        result = installer.install('claude', self.target, backup=True)
        backup = self.target / result['backup_relative_to_target']
        self.assertEqual((backup / 'SKILL.md').read_text(), 'user customized skill')
        removed = installer.uninstall(self.target)
        self.assertEqual(removed['action'], 'uninstalled')
        self.assertEqual((dest / 'SKILL.md').read_text(), 'user customized skill')
        self.assertFalse(backup.exists())

    def test_uninstall_refuses_modified_files(self):
        installer.install('generic', self.target)
        skill = self.target / 'jev-decisions' / 'SKILL.md'
        skill.write_text(skill.read_text() + '\nlocal edit')
        with self.assertRaises(UsageError):
            installer.uninstall(self.target)
        self.assertTrue(skill.exists())

    def test_uninstall_without_manifest_refused(self):
        (self.target / 'jev-decisions').mkdir(parents=True)
        with self.assertRaises(UsageError):
            installer.uninstall(self.target)

    def test_symlink_boundaries(self):
        real = self.home / 'real-skills'
        real.mkdir()
        link = self.home / 'linked-skills'
        link.symlink_to(real, target_is_directory=True)
        with self.assertRaises(UsageError):
            installer.install('codex', link)
        self.target.mkdir(parents=True)
        (self.target / 'jev-decisions').symlink_to(real, target_is_directory=True)
        with self.assertRaises(UsageError):
            installer.install('codex', self.target, backup=True)
        self.assertEqual(list(real.iterdir()), [])

    def test_target_inside_source_refused(self):
        with self.assertRaises(UsageError):
            installer.install('generic', SKILL / 'references')

    def test_runtime_specific_guidance_never_applied(self):
        for runtime, needle in (('claude', 'claude mcp add'), ('hermes', 'hermes mcp add'),
                                ('generic', 'mcp-serve')):
            with self.subTest(runtime=runtime):
                target = self.home / runtime / 'skills'
                result = installer.install(runtime, target)
                self.assertIn(needle, result['mcp_registration_example'])
                self.assertIn('not applied', result['mcp_registration_note'])
        self.assertFalse((self.home / '.claude.json').exists())
        self.assertFalse((self.home / '.codex').exists())
        self.assertFalse((self.home / '.hermes').exists())

    def test_cli_install_output_has_no_absolute_home_path(self):
        result = subprocess.run([sys.executable, '-B', str(CLI), 'install', '--runtime', 'codex',
                                 '--target', str(self.target), '--dry-run'], capture_output=True, text=True,
                                timeout=20, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(str(Path.home()), result.stdout)
        self.assertFalse(self.target.exists())


if __name__ == '__main__':
    unittest.main()
