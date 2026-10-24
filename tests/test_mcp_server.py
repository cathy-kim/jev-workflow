"""stdio MCP server: real subprocess handshake plus in-process live-gate tests."""
import io
import json
import os
import subprocess
import sys
import unittest

from client_fixtures import FAKE_KEYS, OPENAI_RESPONSE, REQUEST, SCRIPTS, fresh
from jev_workflow import mcp_server
from jev_workflow.client import DecisionClient
from jev_workflow.transport import HttpResponse

CLI = SCRIPTS / 'jev_cli.py'
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.endswith('_API_KEY') and k != 'JEV_PROVIDER'}


def rpc(id_, method, params=None):
    message = {'jsonrpc': '2.0', 'id': id_, 'method': method}
    if params is not None:
        message['params'] = params
    return json.dumps(message)


def notification(method):
    return json.dumps({'jsonrpc': '2.0', 'method': method})


def run_server(lines, *args, env=None):
    stdin = '\n'.join(lines) + '\n'
    environment = dict(CLEAN_ENV, PYTHONDONTWRITEBYTECODE='1')
    environment.update(env or {})
    result = subprocess.run([sys.executable, '-B', str(CLI), 'mcp-serve', *args], input=stdin,
                            capture_output=True, text=True, timeout=30, env=environment)
    messages = [json.loads(line) for line in result.stdout.splitlines()]
    return result, messages


INIT = rpc(1, 'initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                             'clientInfo': {'name': 'synthetic-test-client', 'version': '0'}})


class SubprocessHandshakeTests(unittest.TestCase):
    def test_initialize_list_call(self):
        result, messages = run_server([
            INIT, notification('notifications/initialized'), rpc(2, 'tools/list'),
            rpc(3, 'tools/call', {'name': 'jev_validate_request',
                                  'arguments': {'provider': 'openai', 'request': REQUEST}}),
            rpc(4, 'tools/call', {'name': 'jev_list_providers', 'arguments': {}}),
            rpc(5, 'ping'),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([m['id'] for m in messages], [1, 2, 3, 4, 5])
        init = messages[0]['result']
        self.assertEqual(init['protocolVersion'], '2025-06-18')
        self.assertEqual(init['serverInfo']['name'], 'jev-workflow')
        self.assertIn('tools', init['capabilities'])
        names = {tool['name'] for tool in messages[1]['result']['tools']}
        self.assertEqual(names, {'jev_list_providers', 'jev_capabilities', 'jev_validate_request',
                                 'jev_parse_response'})
        for tool in messages[1]['result']['tools']:
            self.assertTrue(tool['annotations']['readOnlyHint'])
            self.assertFalse(tool['annotations']['openWorldHint'])
            self.assertFalse(tool['inputSchema'].get('additionalProperties', True))
        call = messages[2]['result']
        self.assertFalse(call['isError'])
        self.assertEqual(call['structuredContent']['endpoint'], 'https://api.openai.com/v1/decisions')
        self.assertEqual(json.loads(call['content'][0]['text']), call['structuredContent'])
        self.assertEqual(messages[4]['result'], {})

    def test_unknown_version_negotiates_to_supported(self):
        _, messages = run_server([rpc(1, 'initialize', {'protocolVersion': '1999-01-01', 'capabilities': {},
                                                        'clientInfo': {'name': 'x', 'version': '0'}})])
        self.assertIn(messages[0]['result']['protocolVersion'], mcp_server.SUPPORTED_PROTOCOL_VERSIONS)

    def test_protocol_errors(self):
        result, messages = run_server([
            rpc(1, 'tools/list'),  # before initialize
            INIT, '{not json', json.dumps([json.loads(rpc(9, 'ping'))]),
            rpc(2, 'tools/call', {'name': 'jev_decide', 'arguments': {'request': REQUEST}}),
            rpc(3, 'tools/call', {'name': 'jev_validate_request', 'arguments': {'request': REQUEST, 'path': '/etc'}}),
            rpc(4, 'resources/list'),
            'x' * (mcp_server.MAX_LINE_BYTES + 10),
            rpc(5, 'ping'),
        ])
        self.assertEqual(result.returncode, 0)
        by_id = {}
        for message in messages:
            by_id.setdefault(message.get('id'), []).append(message)
        self.assertIn('error', by_id[1][0])
        self.assertEqual(by_id[1][1]['result']['serverInfo']['name'], 'jev-workflow')
        null_errors = [m['error']['code'] for m in by_id[None]]
        self.assertIn(-32700, null_errors)
        self.assertIn(-32600, null_errors)
        self.assertEqual(by_id[2][0]['error']['code'], -32602)  # live tool not registered
        self.assertTrue(by_id[3][0]['result']['isError'])
        self.assertEqual(by_id[4][0]['error']['code'], -32601)
        self.assertEqual(by_id[5][0]['result'], {})

    def test_live_requires_operator_flags(self):
        result, messages = run_server([INIT], '--live-provider', 'openai')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(messages, [])
        result, _ = run_server([INIT], '--enable-live', '--live-provider', 'openai')
        self.assertNotEqual(result.returncode, 0)

    def test_live_tool_listed_only_when_enabled_and_key_redacted(self):
        result, messages = run_server([INIT, rpc(2, 'tools/list')], '--enable-live', '--live-provider', 'openai',
                                      '--max-live-requests', '1', env={'OPENAI_API_KEY': FAKE_KEYS['openai']})
        self.assertEqual(result.returncode, 0, result.stderr)
        tools = {tool['name']: tool for tool in messages[1]['result']['tools']}
        self.assertIn('jev_decide', tools)
        self.assertFalse(tools['jev_decide']['annotations']['readOnlyHint'])
        self.assertTrue(tools['jev_decide']['annotations']['openWorldHint'])
        self.assertNotIn('provider', tools['jev_decide']['inputSchema']['properties'])
        self.assertNotIn(FAKE_KEYS['openai'], result.stdout + result.stderr)


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def send(self, url, headers, body, timeout):
        self.calls += 1
        return self.response


class InProcessLiveTests(unittest.TestCase):
    def make(self, budget=1, response=None):
        transport = FakeTransport(response or HttpResponse(200, json.dumps(fresh(OPENAI_RESPONSE)).encode()))
        live = DecisionClient('openai', environ={'OPENAI_API_KEY': FAKE_KEYS['openai']}, transport=transport)
        server = mcp_server.MCPServer(live_client=live, max_live_requests=budget)
        server.handle(json.loads(INIT))
        return server, transport

    def call(self, server, args, id_=7):
        return server.handle({'jsonrpc': '2.0', 'id': id_, 'method': 'tools/call',
                              'params': {'name': 'jev_decide', 'arguments': args}})

    def test_budget_is_enforced(self):
        server, transport = self.make(budget=1)
        first = self.call(server, {'request': REQUEST})['result']
        self.assertFalse(first['isError'], first)
        self.assertEqual(first['structuredContent']['provider'], 'openai')
        second = self.call(server, {'request': REQUEST})['result']
        self.assertTrue(second['isError'])
        self.assertIn('budget', second['content'][0]['text'])
        self.assertEqual(transport.calls, 1)

    def test_tool_arguments_cannot_change_provider_or_model(self):
        server, transport = self.make()
        for extra in ({'provider': 'typesafe'}, {'model': 'other'}, {'live': True}):
            result = self.call(server, dict({'request': REQUEST}, **extra))['result']
            with self.subTest(extra=extra):
                self.assertTrue(result['isError'])
        self.assertEqual(transport.calls, 0)

    def test_unsupported_payload_fails_before_transport(self):
        server, transport = self.make()
        raw = fresh(REQUEST)
        raw['questions'][0]['criteria'] = {'true': 'y', 'false': 'n'}
        result = self.call(server, {'request': raw})['result']
        self.assertTrue(result['isError'])
        self.assertEqual(result['structuredContent']['error']['code'], 'unsupported_capability')
        self.assertEqual(transport.calls, 0)

    def test_oversize_arguments_rejected(self):
        server, transport = self.make()
        raw = fresh(REQUEST)
        raw['state'] = 'x' * (mcp_server.MAX_ARGUMENT_BYTES + 1)
        result = self.call(server, {'request': raw})['result']
        self.assertTrue(result['isError'])
        self.assertEqual(transport.calls, 0)

    def test_serve_loop_writes_only_jsonrpc(self):
        server = mcp_server.MCPServer()
        stdin = io.BytesIO((INIT + '\n' + rpc(2, 'tools/list') + '\n').encode())
        stdout = io.BytesIO()
        server.serve(stdin, stdout)
        lines = stdout.getvalue().decode().splitlines()
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertEqual(json.loads(line)['jsonrpc'], '2.0')


if __name__ == '__main__':
    unittest.main()
