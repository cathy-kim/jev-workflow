"""Regressions for independent review findings on f69d6ab. Offline, synthetic only."""
import http.server
import json
import threading
import time
import unittest
import urllib.error
from unittest import mock

from client_fixtures import FAKE_KEYS, OPENAI_RESPONSE, OPENROUTER_DECISIONS_RESPONSE, REQUEST, fresh
from jev_workflow import installer, mcp_server
from jev_workflow.client import DecisionClient
from jev_workflow.credentials import redact
from jev_workflow.errors import ResponseError, TransportError, UsageError
from jev_workflow.model import load_request_text, parse_request
from jev_workflow.transport import HttpResponse, UrllibTransport


def choice_request(count):
    raw = fresh(REQUEST)
    raw['questions'] = [{'id': 'c', 'type': 'choice', 'instructions': 'Pick',
                         'options': [{'value': f'o{i}'} for i in range(count)]}]
    return parse_request(raw)


def typesafe_choice_response(probabilities):
    return {'model': 'jev-1.14.0', 'usage': {'input_tokens': 1, 'output_tokens': 1},
            'answers': {'c': {'type': 'choice', 'choice': 'o0', 'confidence': 0.1,
                              'probabilities': probabilities}}}


class DistributionTests(unittest.TestCase):
    def test_incomplete_or_inflated_distributions_rejected(self):
        client = DecisionClient('typesafe', environ={})
        request = choice_request(255)
        for value in (0.0, 0.0089):
            probabilities = {f'o{i}': value for i in range(255)}
            with self.subTest(value=value), self.assertRaises(ResponseError):
                client.parse(request, typesafe_choice_response(probabilities))
        request = choice_request(100)
        probabilities = {f'o{i}': 0.0149 for i in range(100)}
        with self.assertRaises(ResponseError):
            client.parse(request, typesafe_choice_response(probabilities))

    def test_small_rounding_still_accepted(self):
        request = choice_request(3)
        result = DecisionClient('typesafe', environ={}).parse(
            request, typesafe_choice_response({'o0': 0.34, 'o1': 0.33, 'o2': 0.34}))
        self.assertEqual(result.to_dict()['summary']['answered'], 1)


class ScriptedTransport:
    def __init__(self, *steps):
        self.steps, self.calls = list(steps), 0

    def send(self, url, headers, body, timeout):
        self.calls += 1
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class RetrySafetyTests(unittest.TestCase):
    def client(self, transport):
        return DecisionClient('openai', environ={'OPENAI_API_KEY': FAKE_KEYS['openai']}, transport=transport,
                              sleep=lambda s: None, max_attempts=5)

    def test_outcome_unknown_errors_are_not_replayed(self):
        for error in (TransportError('request timed out', code='outcome_unknown'),):
            transport = ScriptedTransport(error, error, error)
            with self.subTest(error=error), self.assertRaises(TransportError) as caught:
                self.client(transport).decide(parse_request(fresh(REQUEST)))
            self.assertEqual(transport.calls, 1)
            self.assertEqual(caught.exception.code, 'outcome_unknown')

    def test_post_send_timeouts_classified_unknown(self):
        class Opener:
            def __init__(self, error):
                self.error = error

            def open(self, request, timeout):
                raise self.error

        for error in (TimeoutError('read'), ConnectionResetError('reset'), OSError('x')):
            transport = UrllibTransport(opener_factory=lambda e=error: Opener(e))
            with self.subTest(error=type(error).__name__), self.assertRaises(TransportError) as caught:
                transport.send('https://api.openai.com/v1/decisions', {}, b'{}', 5)
            self.assertFalse(caught.exception.retryable)
            self.assertEqual(caught.exception.code, 'outcome_unknown')
        for reason in (ConnectionRefusedError('refused'), TimeoutError('connect')):
            transport = UrllibTransport(opener_factory=lambda r=reason: Opener(urllib.error.URLError(r)))
            with self.assertRaises(TransportError) as caught:
                transport.send('https://api.openai.com/v1/decisions', {}, b'{}', 5)
            self.assertTrue(caught.exception.retryable)

    def test_possibly_processed_statuses_not_retried(self):
        for status in (500, 502, 504):
            transport = ScriptedTransport(HttpResponse(status), HttpResponse(200, json.dumps(OPENAI_RESPONSE).encode()))
            with self.subTest(status=status), self.assertRaises(Exception):
                self.client(transport).decide(parse_request(fresh(REQUEST)))
            self.assertEqual(transport.calls, 1)


class _Drip(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        self.send_response(200)
        self.send_header('Content-Length', '100')
        self.end_headers()
        for _ in range(100):
            self.wfile.write(b'x')
            self.wfile.flush()
            time.sleep(0.3)

    def log_message(self, *_args):
        pass


class OverallTimeoutTests(unittest.TestCase):
    def test_drip_feed_cannot_exceed_attempt_timeout(self):
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _Drip)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            from jev_workflow import transport as module
            url = f'http://127.0.0.1:{server.server_port}/x'
            started = time.monotonic()
            with mock.patch.object(module, '_allowed_url', lambda _url: True):
                with self.assertRaises(TransportError) as caught:
                    UrllibTransport().send(url, {}, b'{}', 1)
            self.assertLess(time.monotonic() - started, 2.5)
            self.assertEqual(caught.exception.code, 'outcome_unknown')
        finally:
            server.shutdown()
            server.server_close()


class EnvelopeStrictnessTests(unittest.TestCase):
    def setUp(self):
        self.request = parse_request(fresh(REQUEST))

    def test_openrouter_pinned_provider_required(self):
        response = fresh(OPENROUTER_DECISIONS_RESPONSE)
        response.pop('provider')
        with self.assertRaises(ResponseError):
            DecisionClient('openrouter', environ={}).parse(self.request, response)

    def test_unknown_envelope_fields_rejected(self):
        response = fresh(OPENROUTER_DECISIONS_RESPONSE)
        response['extra'] = 1
        with self.assertRaises(ResponseError):
            DecisionClient('openrouter', environ={}).parse(self.request, response)
        response = fresh(OPENAI_RESPONSE)
        response['extra'] = 1
        with self.assertRaises(ResponseError):
            DecisionClient('openai', environ={}).parse(self.request, response)

    def test_alias_requires_versioned_jev_slug(self):
        response = fresh(OPENROUTER_DECISIONS_RESPONSE)
        response['model'] = 'typesafe/jev-anything'
        with self.assertRaises(ResponseError):
            DecisionClient('openrouter', environ={}).parse(self.request, response)


class InputTypeTests(unittest.TestCase):
    def test_unhashable_values_are_usage_errors(self):
        for mutate in (lambda r: r['questions'][0].update(type=['noul']),
                       lambda r: r.update(images=[{'ref': 'x', 'format': ['png'], 'data_base64': 'AA=='}]),
                       lambda r: r['questions'][0].update(id='a\n')):
            raw = fresh(REQUEST)
            mutate(raw)
            with self.subTest(raw=str(raw)[:60]), self.assertRaises(UsageError):
                parse_request(raw)
        with self.assertRaises(UsageError):
            DecisionClient(['openai'], environ={})

    def test_mcp_list_provider_argument(self):
        server = mcp_server.MCPServer()
        server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})
        result = server.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
            'name': 'jev_capabilities', 'arguments': {'provider': ['openai']}}})['result']
        self.assertTrue(result['isError'])
        self.assertEqual(result['structuredContent']['error']['code'], 'invalid_request')

    def test_duplicate_keys_rejected_everywhere(self):
        with self.assertRaises(UsageError):
            load_request_text('{"state": "a", "state": "b", "questions": []}')
        server = mcp_server.MCPServer()
        import io
        stdin = io.BytesIO(b'{"jsonrpc":"2.0","id":1,"id":2,"method":"ping"}\n')
        stdout = io.BytesIO()
        server.serve(stdin, stdout)
        self.assertEqual(json.loads(stdout.getvalue())['error']['code'], -32700)


class RedactionTests(unittest.TestCase):
    def test_json_escaped_secret_redacted(self):
        secret = 'abc"def\\ghi-0000'
        text = json.dumps({'echo': secret})
        self.assertNotIn('ghi-0000', redact(text, [secret]))


class InstallerRollbackTests(unittest.TestCase):
    def test_failed_swap_restores_previous_install(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / 'skills'
            dest = target / 'jev-decisions'
            dest.mkdir(parents=True)
            (dest / 'SKILL.md').write_text('previous copy')
            real_replace = installer.os.replace
            calls = []

            def flaky(src, dst):
                calls.append((src, dst))
                if len(calls) == 2:
                    raise OSError('synthetic failure')
                return real_replace(src, dst)

            with mock.patch.object(installer.os, 'replace', flaky), self.assertRaises(OSError):
                installer.install('generic', target, backup=True)
            self.assertEqual((dest / 'SKILL.md').read_text(), 'previous copy')
            self.assertEqual(sorted(p.name for p in target.iterdir()), ['jev-decisions'])

    def test_installed_directory_is_readable_and_dotfiles_skipped(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / 'skills'
            installer.install('generic', target)
            mode = (target / 'jev-decisions').stat().st_mode & 0o777
            self.assertEqual(mode & 0o055, 0o055)
            self.assertFalse(any(name.split('/')[-1].startswith('.') for name in installer.source_files()))


if __name__ == '__main__':
    unittest.main()


class _HeaderDrip(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        self.wfile.write(b'HTTP/1.1 200 OK\r\nX-Slow: ')
        for _ in range(40):
            self.wfile.write(b'a')
            self.wfile.flush()
            time.sleep(0.3)

    def log_message(self, *_args):
        pass


class _ErrorBodyDrip(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        self.send_response(500)
        self.send_header('Content-Length', '100')
        self.end_headers()
        for _ in range(100):
            self.wfile.write(b'e')
            self.wfile.flush()
            time.sleep(0.3)

    def log_message(self, *_args):
        pass


class SecondReviewTimeoutTests(unittest.TestCase):
    def assert_bounded(self, handler):
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            from jev_workflow import transport as module
            started = time.monotonic()
            with mock.patch.object(module, '_allowed_url', lambda _url: True):
                with self.assertRaises(TransportError) as caught:
                    UrllibTransport().send(f'http://127.0.0.1:{server.server_port}/x', {}, b'{}', 1)
            self.assertLess(time.monotonic() - started, 2.5)
            self.assertEqual(caught.exception.code, 'outcome_unknown')
        finally:
            server.shutdown()
            server.server_close()

    def test_header_drip_bounded(self):
        self.assert_bounded(_HeaderDrip)

    def test_error_body_drip_bounded(self):
        self.assert_bounded(_ErrorBodyDrip)


class SurrogateTests(unittest.TestCase):
    def test_response_surrogate_rejected(self):
        response = fresh(OPENROUTER_DECISIONS_RESPONSE)
        text = json.dumps(response).replace('gen-dec-synthetic-0001', 'abc\\ud800')
        transport = ScriptedTransport(HttpResponse(200, text.encode()))
        client = DecisionClient('openrouter', environ={'OPENROUTER_API_KEY': FAKE_KEYS['openrouter']},
                                transport=transport)
        with self.assertRaises(ResponseError):
            client.decide(parse_request(fresh(REQUEST)))

    def test_request_surrogate_rejected(self):
        with self.assertRaises(UsageError):
            load_request_text(json.dumps(dict(fresh(REQUEST), state='x')).replace('"x"', '"\\ud800"'))
        raw = fresh(REQUEST)
        raw['state'] = 'bad \ud800'
        with self.assertRaises(UsageError):
            parse_request(raw)
        raw = fresh(REQUEST)
        raw['questions'][0]['instructions'] = 'bad \ud800'
        with self.assertRaises(UsageError):
            parse_request(raw)


class SnapshotMatchTests(unittest.TestCase):
    def test_only_dated_snapshots_match_pinned_slugs(self):
        from jev_workflow import capabilities
        caps = {'match': 'snapshot'}
        for reported in ('gpt-6-luna', 'gpt-6-luna-2026-10-01', 'gpt-6-luna-20261001'):
            self.assertTrue(capabilities.reported_model_ok('gpt-6-luna', reported, caps), reported)
        for reported in ('gpt-6-luna-mini', 'gpt-6-luna-x', 'gpt-6-luna-', 'gpt-6-lunar'):
            self.assertFalse(capabilities.reported_model_ok('gpt-6-luna', reported, caps), reported)
        self.assertTrue(capabilities.reported_model_ok('typesafe/jev-1.13', 'typesafe/jev-1.13-20260917', caps))
        self.assertTrue(capabilities.reported_model_ok('typesafe/jev-1.14', 'typesafe/jev-1.14.0', caps))
        self.assertFalse(capabilities.reported_model_ok('typesafe/jev-1.14', 'typesafe/jev-1.14-lite', caps))


class SecondReviewMiscTests(unittest.TestCase):
    def test_key_with_quote_blocked_before_send(self):
        key = 'ab"cdefghij-0000'
        raw = fresh(REQUEST)
        raw['state'] = 'leak ' + key
        transport = ScriptedTransport()
        client = DecisionClient('openai', environ={'OPENAI_API_KEY': key}, transport=transport)
        with self.assertRaises(UsageError):
            client.decide(parse_request(raw))
        self.assertEqual(transport.calls, 0)

    def test_boolean_usage_metadata_accepted_but_not_as_counts(self):
        response = fresh(OPENROUTER_DECISIONS_RESPONSE)
        response['usage']['is_byok'] = False
        result = DecisionClient('openrouter', environ={}).parse(parse_request(fresh(REQUEST)), response).to_dict()
        self.assertIs(result['usage']['is_byok'], False)
        response['usage']['input_tokens'] = True
        with self.assertRaises(ResponseError):
            DecisionClient('openrouter', environ={}).parse(parse_request(fresh(REQUEST)), response)
