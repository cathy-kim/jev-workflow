"""Live-path behavior with synthetic transports. No DNS or provider calls."""
import http.client
import http.server
import json
import threading
import unittest
import urllib.error
import urllib.request

from client_fixtures import FAKE_KEYS, OPENAI_RESPONSE, REQUEST, TYPESAFE_RESPONSE, fresh
from jev_workflow import transport as transport_module
from jev_workflow.client import DecisionClient
from jev_workflow.errors import CredentialError, ProviderError, ResponseError, TransportError, UsageError
from jev_workflow.model import parse_request
from jev_workflow.transport import HttpResponse, UrllibTransport


class FakeTransport:
    """Scripted synthetic responses; records every call."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.calls = []

    def send(self, url, headers, body, timeout):
        self.calls.append({'url': url, 'headers': dict(headers), 'body': body, 'timeout': timeout})
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def ok(document):
    return HttpResponse(200, json.dumps(document).encode('utf-8'))


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make(provider, steps, environ=None, **kwargs):
    fake = FakeTransport(*steps)
    clock = FakeClock()
    env = {name: value for name, value in (environ if environ is not None else {
        'OPENAI_API_KEY': FAKE_KEYS['openai'], 'TYPESAFE_API_KEY': FAKE_KEYS['typesafe'],
        'OPENROUTER_API_KEY': FAKE_KEYS['openrouter']}).items()}
    client = DecisionClient(provider, environ=env, transport=fake, sleep=clock.sleep, clock=clock.clock, **kwargs)
    return client, fake, clock


REQ = parse_request(fresh(REQUEST))


class CredentialTests(unittest.TestCase):
    def test_only_selected_provider_key_is_sent(self):
        client, fake, _ = make('openai', [ok(fresh(OPENAI_RESPONSE))])
        client.decide(REQ)
        auth = fake.calls[0]['headers']['Authorization']
        self.assertEqual(auth, 'Bearer ' + FAKE_KEYS['openai'])
        self.assertEqual(fake.calls[0]['url'], 'https://api.openai.com/v1/decisions')
        for other in ('typesafe', 'openrouter'):
            self.assertNotIn(FAKE_KEYS[other], json.dumps(fake.calls[0]['headers']))

    def test_missing_key_fails_offline_without_transport(self):
        client, fake, _ = make('typesafe', [], environ={'OPENAI_API_KEY': FAKE_KEYS['openai']})
        with self.assertRaises(CredentialError) as caught:
            client.decide(REQ)
        self.assertEqual(caught.exception.code, 'credential_missing')
        self.assertIn('TYPESAFE_API_KEY', str(caught.exception))
        self.assertEqual(fake.calls, [])

    def test_malformed_key_rejected(self):
        for bad in ('short', 'has space inside-xxxx', 'line\nbreak-xxxxxxxx'):
            client, fake, _ = make('openai', [], environ={'OPENAI_API_KEY': bad})
            with self.subTest(bad=bad), self.assertRaises(CredentialError):
                client.decide(REQ)
            self.assertEqual(fake.calls, [])

    def test_key_never_appears_in_output(self):
        response = fresh(OPENAI_RESPONSE)
        client, _, _ = make('openai', [ok(response)])
        text = json.dumps(client.decide(REQ).to_dict())
        self.assertNotIn(FAKE_KEYS['openai'], text)

    def test_credential_echo_rejected(self):
        response = fresh(OPENAI_RESPONSE)
        response['echo'] = FAKE_KEYS['openai']
        client, _, _ = make('openai', [ok(response)])
        with self.assertRaises(ResponseError) as caught:
            client.decide(REQ)
        self.assertNotIn(FAKE_KEYS['openai'], str(caught.exception))

    def test_request_containing_key_not_sent(self):
        raw = fresh(REQUEST)
        raw['state'] = 'leaked ' + FAKE_KEYS['openai']
        client, fake, _ = make('openai', [])
        with self.assertRaises(UsageError):
            client.decide(parse_request(raw))
        self.assertEqual(fake.calls, [])

    def test_401_maps_to_credential_rejected_without_retry(self):
        client, fake, _ = make('openai', [HttpResponse(401, b'{"error": "synthetic-openai-key-0000"}')])
        with self.assertRaises(CredentialError) as caught:
            client.decide(REQ)
        self.assertEqual(caught.exception.code, 'credential_rejected')
        self.assertNotIn(FAKE_KEYS['openai'], str(caught.exception))
        self.assertEqual(len(fake.calls), 1)


class RetryTests(unittest.TestCase):
    def test_retry_on_429_then_success_respects_retry_after(self):
        client, fake, clock = make('typesafe', [HttpResponse(429, b'', {'retry-after': '2'}),
                                                ok(fresh(TYPESAFE_RESPONSE))])
        result = client.decide(REQ).to_dict()
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(clock.sleeps, [2.0])
        self.assertEqual(result['provenance']['attempts'], 2)
        self.assertEqual(len(result['provenance']['request_sha256']), 64)

    def test_retry_after_capped(self):
        client, _, clock = make('typesafe', [HttpResponse(529, b'', {'retry-after': '9999'}),
                                             ok(fresh(TYPESAFE_RESPONSE))], deadline=300)
        client.decide(REQ)
        self.assertEqual(clock.sleeps, [30.0])

    def test_budget_exhausted(self):
        client, fake, _ = make('openai', [HttpResponse(503)] * 3, max_attempts=3)
        with self.assertRaises(ProviderError) as caught:
            client.decide(REQ)
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(len(fake.calls), 3)

    def test_deadline_stops_retry(self):
        client, fake, _ = make('openai', [HttpResponse(429, b'', {'retry-after': '20'})] * 3, deadline=10)
        with self.assertRaises(ProviderError):
            client.decide(REQ)
        self.assertEqual(len(fake.calls), 1)

    def test_non_retryable_statuses_stop_immediately(self):
        for status in (400, 413, 422, 402):
            client, fake, _ = make('openai', [HttpResponse(status, b'{"secret": "body"}')])
            with self.subTest(status=status), self.assertRaises(ProviderError) as caught:
                client.decide(REQ)
            self.assertNotIn('body', str(caught.exception))
            self.assertEqual(len(fake.calls), 1)

    def test_retryable_transport_errors_and_non_retryable_protocol_errors(self):
        client, fake, _ = make('openai', [TransportError('connection failed (ConnectionResetError)', retryable=True),
                                          ok(fresh(OPENAI_RESPONSE))])
        client.decide(REQ)
        self.assertEqual(len(fake.calls), 2)
        client, fake, _ = make('openai', [TransportError('invalid HTTP response (IncompleteRead)')])
        with self.assertRaises(TransportError):
            client.decide(REQ)
        self.assertEqual(len(fake.calls), 1)

    def test_redirect_refused(self):
        client, fake, _ = make('openai', [HttpResponse(307, b'', {})])
        with self.assertRaises(ProviderError) as caught:
            client.decide(REQ)
        self.assertEqual(caught.exception.code, 'redirect_refused')
        self.assertEqual(len(fake.calls), 1)

    def test_openrouter_allowed_providers_diagnostic(self):
        body = json.dumps({'error': {'code': 404, 'message': 'No allowed providers are available',
                                     'metadata': {'failed_routing_step': 'Filter by Allowed Providers'}}}).encode()
        client, _, _ = make('openrouter', [HttpResponse(404, body)])
        with self.assertRaises(ProviderError) as caught:
            client.decide(REQ)
        self.assertEqual(caught.exception.code, 'openrouter_provider_not_allowed')

    def test_malformed_success_body(self):
        for body in (b'not json', b'{"a": NaN}', b'{"a": 1, "a": 2}', b'\xff\xfe'):
            client, _, _ = make('openai', [HttpResponse(200, body)])
            with self.subTest(body=body), self.assertRaises(ResponseError):
                client.decide(REQ)

    def test_invalid_bounds(self):
        for kwargs in ({'timeout': 0}, {'timeout': float('inf')}, {'max_attempts': 9}, {'deadline': -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(UsageError):
                DecisionClient('openai', environ={}, **kwargs)


class _RedirectHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - stdlib naming
        self.send_response(302)
        self.send_header('Location', 'http://127.0.0.1:9/elsewhere')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def log_message(self, *_args):
        pass


class UrllibTransportTests(unittest.TestCase):
    def test_opener_disables_proxies_and_redirects(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {'HTTPS_PROXY': 'http://127.0.0.1:9', 'ALL_PROXY': 'http://127.0.0.1:9'}):
            opener = transport_module.build_opener()
        # An empty ProxyHandler registers no *_open methods, so no proxy route exists.
        proxy_handlers = [h for h in opener.handlers if isinstance(h, urllib.request.ProxyHandler)]
        self.assertEqual(proxy_handlers, [])
        redirect = [h for h in opener.handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
        self.assertEqual([type(h).__name__ for h in redirect], ['_NoRedirect'])

    def test_loopback_redirect_is_not_followed(self):
        server = http.server.HTTPServer(('127.0.0.1', 0), _RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/decisions'
            with self.assertRaises(urllib.error.HTTPError) as caught:
                transport_module.build_opener().open(urllib.request.Request(url, data=b'{}', method='POST'), timeout=5)
            self.assertEqual(caught.exception.code, 302)
            caught.exception.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_non_https_refused(self):
        with self.assertRaises(TransportError):
            UrllibTransport().send('http://api.openai.com/v1/decisions', {}, b'{}', 5)
        with self.assertRaises(TransportError):
            UrllibTransport().send('https://user:pw@api.openai.com/v1/decisions', {}, b'{}', 5)

    def opener_raising(self, error):
        class Opener:
            def open(self, request, timeout):
                raise error
        return lambda: Opener()

    def test_protocol_and_network_errors_are_sanitized(self):
        secret = 'synthetic-secret-in-exception'
        cases = [
            (http.client.IncompleteRead(secret.encode()), False),
            (http.client.RemoteDisconnected(secret), False),
            (urllib.error.URLError(TimeoutError(secret)), True),
            (urllib.error.URLError(ConnectionRefusedError(secret)), True),
            (TimeoutError(secret), False),  # after send: outcome unknown, never replayed
        ]
        for error, retryable in cases:
            with self.subTest(error=type(error).__name__):
                transport = UrllibTransport(opener_factory=self.opener_raising(error))
                with self.assertRaises(TransportError) as caught:
                    transport.send('https://api.openai.com/v1/decisions', {}, b'{}', 5)
                self.assertNotIn(secret, str(caught.exception))
                self.assertEqual(caught.exception.retryable, retryable)
                self.assertIsNone(caught.exception.__cause__)

    def test_response_size_limit_and_incomplete_read_during_body(self):
        class Response:
            status = 200
            headers = {}

            def __init__(self, data=None, error=None):
                self.data, self.error = data, error

            def read(self, size):
                if self.error:
                    raise self.error
                return self.data[:size]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def factory(response):
            class Opener:
                def open(self, request, timeout):
                    return response
            return lambda: Opener()

        big = UrllibTransport(max_response_bytes=10, opener_factory=factory(Response(b'x' * 11)))
        with self.assertRaises(TransportError) as caught:
            big.send('https://api.openai.com/v1/decisions', {}, b'{}', 5)
        self.assertEqual(caught.exception.code, 'response_too_large')
        broken = UrllibTransport(opener_factory=factory(Response(error=http.client.IncompleteRead(b'partial secret'))))
        with self.assertRaises(TransportError) as caught:
            broken.send('https://api.openai.com/v1/decisions', {}, b'{}', 5)
        self.assertNotIn('secret', str(caught.exception))

    def test_http_error_body_is_bounded_and_returned_as_status(self):
        import io

        class Opener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError('https://api.openai.com/v1/decisions', 503, 'x',
                                             {'Retry-After': '3', 'Set-Cookie': 'drop'},
                                             io.BytesIO(b'y' * 100_000))

        response = UrllibTransport(opener_factory=lambda: Opener()).send(
            'https://api.openai.com/v1/decisions', {}, b'{}', 5)
        self.assertEqual(response.status, 503)
        self.assertLessEqual(len(response.body), transport_module.MAX_ERROR_BODY_BYTES)
        self.assertEqual(response.headers, {'retry-after': '3'})


if __name__ == '__main__':
    unittest.main()
