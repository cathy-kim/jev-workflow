"""CLI subprocess tests. Offline commands run under a network/secret-file audit guard."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from client_fixtures import (FAKE_KEYS, OPENAI_RESPONSE, PNG_1X1, REQUEST, SCRIPTS, TYPESAFE_RESPONSE, fresh,
                             structured_response)

CLI = SCRIPTS / 'jev_cli.py'
GUARD = (
    "import sys, runpy\n"
    "def guard(event, args):\n"
    "    if event.startswith(('socket.', 'urllib.', 'http.client.', 'subprocess.')) or event in "
    "('os.system', 'os.posix_spawn', 'os.spawn', 'os.exec'):\n"
    "        raise RuntimeError('FORBIDDEN_EXTERNAL_ACTION ' + event)\n"
    "    if event == 'open' and isinstance(args[0], str):\n"
    "        parts = args[0].replace(chr(92), '/').split('/')\n"
    "        if any(p.startswith('.env') or p in ('.ssh', '.aws', '.netrc', '.npmrc') for p in parts):\n"
    "            raise RuntimeError('FORBIDDEN_SECRET_LOOKUP')\n"
    "sys.addaudithook(guard)\n"
    "sys.argv = sys.argv[1:]\n"
    "runpy.run_path(sys.argv[0], run_name='__main__')\n"
)
CLEAN_ENV = {k: v for k, v in os.environ.items()
             if not k.endswith('_API_KEY') and k not in ('JEV_PROVIDER', 'JEV_MODEL', 'JEV_BASE_URL')}


def run(args, *, stdin=None, env=None, guard=True, cwd=None):
    command = [sys.executable, '-B', '-c', GUARD, str(CLI)] if guard else [sys.executable, '-B', str(CLI)]
    environment = dict(CLEAN_ENV, PYTHONDONTWRITEBYTECODE='1')
    environment.update(env or {})
    return subprocess.run(command + list(map(str, args)), input=stdin, capture_output=True, text=True,
                          timeout=30, env=environment, cwd=cwd)


class CliOfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jev-cli-')
        self.dir = Path(self.tmp.name)
        self.request = self.dir / 'request.json'
        self.request.write_text(json.dumps(REQUEST))

    def tearDown(self):
        self.tmp.cleanup()

    def assert_json(self, result, code=0):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_version_and_help(self):
        result = run(['--version'])
        self.assertEqual(result.returncode, 0)
        self.assertIn('1.2.0', result.stdout)
        for command in ([], ['decide'], ['ask'], ['providers'], ['doctor'], ['parse'], ['install'], ['mcp-serve']):
            with self.subTest(command=command):
                result = run(command + ['--help'])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('/Users/', result.stdout)

    def test_providers_and_capabilities(self):
        matrix = self.assert_json(run(['providers']))
        self.assertEqual(set(matrix['providers']), {'openai', 'typesafe', 'openrouter'})
        caps = self.assert_json(run(['capabilities', '--provider', 'typesafe', '--model', 'jev-1.13.0']))
        self.assertEqual(caps['model'], 'jev-1.13.0')
        self.assertFalse(caps['model_capabilities']['box'])

    def test_doctor_reads_no_credentials(self):
        env = {'OPENAI_API_KEY': FAKE_KEYS['openai'], 'TYPESAFE_API_KEY': FAKE_KEYS['typesafe']}
        report = self.assert_json(run(['doctor'], env=env))
        self.assertEqual(report['network'], 'not contacted')
        self.assertEqual(report['credentials'], 'not inspected')
        self.assertNotIn(FAKE_KEYS['openai'], json.dumps(report))
        self.assertNotIn('set', json.dumps(report.get('credential_env', {})).lower())

    def test_dry_run_each_provider(self):
        expected = {'openai': 'https://api.openai.com/v1/decisions',
                    'typesafe': 'https://api.typesafe.ai/v1/systemone',
                    'openrouter': 'https://openrouter.ai/api/alpha/decisions'}
        for provider, endpoint in expected.items():
            with self.subTest(provider=provider):
                env = {f'{provider.upper()}_API_KEY': FAKE_KEYS[provider]}
                preview = self.assert_json(run(['decide', '--provider', provider, '--request', self.request,
                                                '--dry-run'], env=env))
                self.assertEqual(preview['endpoint'], endpoint)
                self.assertEqual(preview['network'], 'not contacted')
                self.assertNotIn(FAKE_KEYS[provider], json.dumps(preview))

    def test_stdin_request_and_compact(self):
        result = run(['validate', '--provider', 'openai', '--request', '-', '--compact'], stdin=json.dumps(REQUEST))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.strip().splitlines()), 1)

    def test_decide_requires_explicit_mode(self):
        result = run(['decide', '--request', self.request])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')

    def test_provider_precedence(self):
        default = self.assert_json(run(['validate', '--request', self.request]))
        self.assertEqual((default['provider'], default['config']['provider_source']), ('openrouter', 'default'))
        env = self.assert_json(run(['validate', '--request', self.request], env={'JEV_PROVIDER': 'openai'}))
        self.assertEqual((env['provider'], env['config']['provider_source']), ('openai', 'env:JEV_PROVIDER'))
        flag = self.assert_json(run(['validate', '--provider', 'typesafe', '--request', self.request],
                                    env={'JEV_PROVIDER': 'openai'}))
        self.assertEqual((flag['provider'], flag['config']['provider_source']), ('typesafe', 'flag'))

    def test_endpoint_and_model_env_are_ignored(self):
        env = {'JEV_BASE_URL': 'https://attacker.invalid/x', 'JEV_MODEL': 'other/model',
               'HTTPS_PROXY': 'http://127.0.0.1:9'}
        preview = self.assert_json(run(['validate', '--request', self.request], env=env))
        self.assertEqual(preview['endpoint'], 'https://openrouter.ai/api/alpha/decisions')
        self.assertEqual(preview['model'], '~typesafe/jev-latest')

    def test_errors_are_json_with_stable_exit_codes(self):
        bad = self.dir / 'bad.json'
        bad.write_text('{"state": "x", "questions": []}')
        result = run(['validate', '--request', bad])
        error = self.assert_json(result, 2)
        self.assertEqual(error['error']['code'], 'invalid_request')
        self.assertIn('invalid_request', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        raw = fresh(REQUEST)
        raw['questions'][0]['criteria'] = {'true': 'y', 'false': 'n'}
        capability = self.dir / 'cap.json'
        capability.write_text(json.dumps(raw))
        self.assert_json(run(['validate', '--provider', 'openai', '--request', capability]), 6)
        missing = run(['validate', '--request', self.dir / 'missing.json'])
        self.assertEqual(missing.returncode, 2)
        self.assertNotIn(str(self.dir), missing.stdout + missing.stderr)

    def test_live_without_key_fails_offline(self):
        result = run(['decide', '--provider', 'openai', '--request', self.request, '--live'])
        error = self.assert_json(result, 3)
        self.assertEqual(error['error']['code'], 'credential_missing')

    def test_parse_saved_responses(self):
        cases = [('openai', [], OPENAI_RESPONSE), ('typesafe', [], TYPESAFE_RESPONSE),
                 ('openrouter', ['--openrouter-mode', 'structured', '--model', 'example/judge-model'],
                  structured_response())]
        for provider, extra, response in cases:
            path = self.dir / f'{provider}.response.json'
            path.write_text(json.dumps(response))
            with self.subTest(provider=provider):
                result = self.assert_json(run(['parse', '--provider', provider, *extra,
                                               '--request', self.request, '--response', path]))
                self.assertEqual(result['schema_version'], 'jev.result.v1')
        broken = self.dir / 'broken.json'
        broken.write_text(json.dumps({'answers': []}))
        self.assert_json(run(['parse', '--provider', 'openai', '--request', self.request, '--response', broken]), 5)

    def test_ask_builder_preserves_order(self):
        preview = self.assert_json(run([
            'ask', '--provider', 'openai', '--dry-run', '--state', 'Synthetic: charged twice',
            '--noul', 'Is it about billing?',
            '--choice', 'Which team?', '--option', 'billing=Payments', '--option', 'technical',
            '--score', 'How urgent?', '--level', 'Low', '--level', 'High=Blocking']))
        questions = preview['body']['questions']
        self.assertEqual([q['name'] for q in questions], ['q1', 'q2', 'q3'])
        self.assertEqual(questions[1]['choices'], [{'value': 'billing', 'description': 'Payments'},
                                                   {'value': 'technical'}])
        self.assertEqual(questions[2]['levels'][1], {'label': 'High', 'description': 'Blocking'})
        orphan = run(['ask', '--dry-run', '--state', 'x', '--option', 'a'])
        self.assertEqual(orphan.returncode, 2)

    def test_image_flag_requires_consent_and_typesafe(self):
        image = self.dir / 'square.png'
        image.write_bytes(PNG_1X1)
        raw = fresh(REQUEST)
        raw['state'] = {'photo': 'img-1'}
        raw['questions'] = [{'id': 'present', 'type': 'noul', 'instructions': 'Square in `photo`?'},
                            {'id': 'where', 'type': 'box', 'instructions': 'the square in `photo`'}]
        path = self.dir / 'image-request.json'
        path.write_text(json.dumps(raw))
        args = ['validate', '--provider', 'typesafe', '--request', path, '--image', f'img-1={image}']
        self.assert_json(run(args), 6)
        preview = self.assert_json(run(args + ['--experimental-images']))
        self.assertEqual(preview['headers']['TypeSafe-Danger-Zone-Images'], 'true')
        self.assertEqual(preview['body']['assets']['img-1']['data_base64'], base64.b64encode(PNG_1X1).decode())
        self.assert_json(run(['validate', '--provider', 'openai', '--request', path, '--image', f'img-1={image}',
                              '--experimental-images']), 6)
        text = self.dir / 'not-image.png'
        text.write_text('plain text')
        self.assert_json(run(['validate', '--provider', 'typesafe', '--request', path,
                              '--image', f'img-1={text}', '--experimental-images']), 2)

    def test_shipped_synthetic_examples_parse(self):
        examples = SCRIPTS / 'examples' / 'providers'
        request = examples / 'request.synthetic.json'
        cases = [(['--provider', 'openai'], 'openai'), (['--provider', 'typesafe'], 'typesafe'),
                 (['--provider', 'openrouter'], 'openrouter-decisions'),
                 (['--provider', 'openrouter', '--openrouter-mode', 'structured', '--model', 'example/judge-model'],
                  'openrouter-structured')]
        for flags, name in cases:
            with self.subTest(name=name):
                result = self.assert_json(run(['parse', *flags, '--request', request,
                                               '--response', examples / f'{name}.response.synthetic.json']))
                self.assertEqual(result['summary']['answered'] + result['summary']['refused']
                                 + result['summary']['not_applicable'], 3)

    def test_import_has_no_side_effects(self):
        probe = ("import sys\n"
                 "def guard(event, args):\n"
                 "    if event.startswith(('socket.', 'urllib.', 'http.client.', 'subprocess.')):\n"
                 "        raise RuntimeError(event)\n"
                 "    if event == 'open' and isinstance(args[0], str) and not args[0].endswith(('.py', '.pyc')) "
                 "and '__pycache__' not in args[0] and not args[0].startswith(sys.prefix) "
                 "and not args[0].startswith(sys.base_prefix):\n"
                 "        raise RuntimeError('open ' + args[0])\n"
                 "sys.addaudithook(guard)\n"
                 "sys.path.insert(0, sys.argv[1])\n"
                 "import jev_workflow.client, jev_workflow.cli, jev_workflow.mcp_server, jev_workflow.installer\n"
                 "print('ok')\n")
        result = subprocess.run([sys.executable, '-B', '-c', probe, str(SCRIPTS)], capture_output=True, text=True,
                                timeout=20, env=dict(CLEAN_ENV, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(result.stdout.strip(), 'ok', result.stderr)


if __name__ == '__main__':
    unittest.main()


class CliSecondReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jev-cli2-')
        self.request = Path(self.tmp.name) / 'request.json'
        self.request.write_text(json.dumps(REQUEST))

    def tearDown(self):
        self.tmp.cleanup()

    def test_live_requires_explicit_provider(self):
        result = run(['decide', '--request', self.request, '--live'])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('--provider', json.loads(result.stdout)['error']['message'])
        env_result = run(['decide', '--request', self.request, '--live'], env={'JEV_PROVIDER': 'openai'})
        self.assertEqual(json.loads(env_result.stdout)['error']['code'], 'credential_missing')

    def test_images_wrong_type_is_usage_error(self):
        raw = fresh(REQUEST)
        raw['images'] = 5
        path = Path(self.tmp.name) / 'bad-images.json'
        path.write_text(json.dumps(raw))
        image = Path(self.tmp.name) / 'a.png'
        image.write_bytes(PNG_1X1)
        result = run(['validate', '--provider', 'typesafe', '--request', path, '--image', f'x={image}'])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'invalid_request')
