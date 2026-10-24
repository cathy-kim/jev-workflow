"""Standard-library stdio MCP server (JSON-RPC 2.0, newline-delimited).

Default mode is offline: listing, capabilities, request validation/preview and
saved-response parsing. A paid ``jev_decide`` tool exists only when the
operator starts the server with ``--enable-live --live-provider P
--max-live-requests N``; tool arguments can never enable live mode, switch the
provider or model, or raise the budget. Tool annotations are hints for clients,
not billing consent. stdout carries only JSON-RPC messages.
"""
import argparse
import json
import sys

from . import VERSION, capabilities
from .client import DecisionClient
from .credentials import redact
from .errors import JevError, UsageError
from .model import parse_request

SUPPORTED_PROTOCOL_VERSIONS = ('2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05')
MAX_LINE_BYTES = 1024 * 1024
MAX_ARGUMENT_BYTES = 512 * 1024
MAX_LIVE_REQUESTS = 1000

_PROVIDER_PROPS = {
    'provider': {'type': 'string', 'enum': list(capabilities.provider_names())},
    'model': {'type': 'string', 'maxLength': 200},
    'openrouter_mode': {'type': 'string', 'enum': list(capabilities.OPENROUTER_MODES)},
}
_OFFLINE = {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}


def _schema(properties, required=()):
    return {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}


OFFLINE_TOOLS = {
    'jev_list_providers': {
        'description': 'List the three providers, their routes, pinned default models and capabilities. Offline.',
        'inputSchema': _schema({}),
    },
    'jev_capabilities': {
        'description': 'Capabilities for one provider/model/route. Offline; reads no credential.',
        'inputSchema': _schema(dict(_PROVIDER_PROPS), ['provider']),
    },
    'jev_validate_request': {
        'description': 'Validate a jev.request.v1 object and return the exact provider payload that a live call '
                       'would send (dry run). Offline; no network, no credential.',
        'inputSchema': _schema(dict(_PROVIDER_PROPS, request={'type': 'object'}), ['request']),
    },
    'jev_parse_response': {
        'description': 'Normalize a saved provider response against its request, failing closed on contract '
                       'violations. Offline.',
        'inputSchema': _schema(dict(_PROVIDER_PROPS, request={'type': 'object'}, response={}),
                               ['request', 'response']),
    },
}


class _ToolError(Exception):
    def __init__(self, document):
        super().__init__(document['error']['message'])
        self.document = document


def _error_document(code, message):
    return {'schema_version': 'jev.error.v1', 'error': {'code': code, 'message': message}}


class MCPServer:
    def __init__(self, *, live_client=None, max_live_requests=0):
        if live_client is not None and not 1 <= max_live_requests <= MAX_LIVE_REQUESTS:
            raise UsageError(f'--max-live-requests must be 1-{MAX_LIVE_REQUESTS} when live mode is enabled')
        self._live = live_client
        self._remaining = max_live_requests if live_client is not None else 0
        self._initialized = False

    # ------------------------------------------------------------------ tools
    def tools(self):
        tools = [dict(name=name, title=name.replace('_', ' '), annotations=dict(_OFFLINE, title=name), **spec)
                 for name, spec in OFFLINE_TOOLS.items()]
        if self._live is not None:
            tools.append({
                'name': 'jev_decide',
                'title': 'jev decide (paid live call)',
                'description': (f'PAID live call to the operator-selected provider {self._live.provider} '
                                f'({self._live.route}, model {self._live.model}). Sends the request state to that '
                                'provider. Bounded by the operator budget for this server process.'),
                'inputSchema': _schema({'request': {'type': 'object'}}, ['request']),
                'annotations': {'title': 'jev decide (paid)', 'readOnlyHint': False, 'destructiveHint': False,
                                'idempotentHint': False, 'openWorldHint': True},
            })
        return tools

    def _call(self, name, arguments):
        if name == 'jev_decide' and self._live is not None:
            self._check_args(arguments, {'request'}, {'request'})
            request = parse_request(arguments['request'])
            if self._remaining <= 0:
                raise _ToolError(_error_document('live_budget_exhausted',
                                                 'live request budget for this server process is exhausted'))
            self._live.prepare(request)  # capability errors fail before spending budget
            self._remaining -= 1
            return self._live.decide(request).to_dict()
        if name not in OFFLINE_TOOLS:
            raise KeyError(name)
        if name == 'jev_list_providers':
            self._check_args(arguments, set(), set())
            return capabilities.matrix()
        allowed = set(OFFLINE_TOOLS[name]['inputSchema']['properties'])
        required = set(OFFLINE_TOOLS[name]['inputSchema']['required'])
        self._check_args(arguments, allowed, required)
        provider = arguments.get('provider', capabilities.DEFAULT_PROVIDER)
        if name == 'jev_capabilities':
            route = capabilities.route_key(provider, arguments.get('openrouter_mode'))
            model, caps = capabilities.resolve_model(provider, arguments.get('model'), route)
            caps.pop('alias_pattern', None)
            return {'schema_version': 'jev.capabilities.v1', 'provider': provider, 'model': model,
                    'credential_env': capabilities.credential_env(provider), 'model_capabilities': caps,
                    'route': {k: v for k, v in capabilities.route_spec(provider, route).items() if k != 'models'}}
        client = DecisionClient(provider, arguments.get('model'), openrouter_mode=arguments.get('openrouter_mode'))
        request = parse_request(arguments['request'])
        if name == 'jev_validate_request':
            return dict(client.prepare(request).to_dict(), valid=True)
        return client.parse(request, arguments['response'],
                            provenance={'source': 'saved response (offline parse)'}).to_dict()

    @staticmethod
    def _check_args(arguments, allowed, required):
        if not isinstance(arguments, dict):
            raise UsageError('tool arguments must be an object')
        unknown = sorted(set(arguments) - allowed)
        if unknown:
            raise UsageError(f'unknown tool argument(s): {", ".join(unknown)}')
        missing = sorted(required - set(arguments))
        if missing:
            raise UsageError(f'missing tool argument(s): {", ".join(missing)}')

    def _tool_result(self, params):
        name = params.get('name') if isinstance(params, dict) else None
        arguments = params.get('arguments', {}) if isinstance(params, dict) else None
        if not isinstance(name, str):
            return None, (-32602, 'tools/call requires a tool name')
        if name not in OFFLINE_TOOLS and not (name == 'jev_decide' and self._live is not None):
            return None, (-32602, f'Unknown tool: {name[:64]}')
        try:
            size = len(json.dumps(arguments, ensure_ascii=False, allow_nan=False).encode('utf-8'))
        except (TypeError, ValueError, RecursionError):
            size = MAX_ARGUMENT_BYTES + 1
        try:
            if size > MAX_ARGUMENT_BYTES:
                raise UsageError(f'tool arguments exceed {MAX_ARGUMENT_BYTES} bytes')
            document, is_error = self._call(name, arguments), False
        except JevError as error:
            document, is_error = error.to_dict(), True
        except _ToolError as error:
            document, is_error = error.document, True
        except Exception as error:  # noqa: BLE001 - sanitized, never a traceback
            document, is_error = _error_document('internal_error', type(error).__name__), True
        text = json.dumps(document, ensure_ascii=False, allow_nan=False)
        return {'content': [{'type': 'text', 'text': text}], 'structuredContent': document,
                'isError': is_error}, None

    # ------------------------------------------------------------------ protocol
    def handle(self, message):
        if isinstance(message, list):
            return _rpc_error(None, -32600, 'JSON-RPC batching is not supported')
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0' or not isinstance(message.get('method'), str):
            return _rpc_error(message.get('id') if isinstance(message, dict) else None, -32600, 'Invalid Request')
        method = message['method']
        if 'id' not in message:
            return None  # notifications (initialized, cancelled, ...) need no response
        id_ = message['id']
        if isinstance(id_, bool) or not isinstance(id_, (str, int)) or id_ is None:
            return _rpc_error(None, -32600, 'Invalid Request id')
        params = message.get('params', {})
        if method == 'initialize':
            requested = params.get('protocolVersion') if isinstance(params, dict) else None
            version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
            self._initialized = True
            mode = 'live tool enabled by operator' if self._live is not None else 'offline tools only'
            return _rpc_result(id_, {
                'protocolVersion': version,
                'capabilities': {'tools': {'listChanged': False}},
                'serverInfo': {'name': 'jev-workflow', 'title': 'Jev Workflow decisions', 'version': VERSION},
                'instructions': f'Typed decision tools ({mode}). Validate requests offline before any live call.',
            })
        if method == 'ping':
            return _rpc_result(id_, {})
        if not self._initialized:
            return _rpc_error(id_, -32600, 'Server not initialized')
        if method == 'tools/list':
            return _rpc_result(id_, {'tools': self.tools()})
        if method == 'tools/call':
            result, error = self._tool_result(params)
            return _rpc_error(id_, *error) if error else _rpc_result(id_, result)
        return _rpc_error(id_, -32601, 'Method not found')

    def serve(self, stdin, stdout):
        while True:
            line = stdin.readline(MAX_LINE_BYTES + 1)
            if not line:
                return
            if len(line) > MAX_LINE_BYTES and not line.endswith(b'\n'):
                while True:
                    rest = stdin.readline(MAX_LINE_BYTES)
                    if not rest or rest.endswith(b'\n'):
                        break
                self._write(stdout, _rpc_error(None, -32700, f'message exceeds {MAX_LINE_BYTES} bytes'))
                continue
            if not line.strip():
                continue
            try:
                message = json.loads(line.decode('utf-8'))
            except (UnicodeDecodeError, ValueError, RecursionError):
                self._write(stdout, _rpc_error(None, -32700, 'Parse error'))
                continue
            self._write(stdout, self.handle(message))

    def _write(self, stdout, response):
        if response is None:
            return
        text = json.dumps(response, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        secrets = self._live.secrets() if self._live is not None and hasattr(self._live, 'secrets') else []
        stdout.write((redact(text, secrets) + '\n').encode('utf-8'))
        stdout.flush()


def _rpc_result(id_, result):
    return {'jsonrpc': '2.0', 'id': id_, 'result': result}


def _rpc_error(id_, code, message):
    return {'jsonrpc': '2.0', 'id': id_, 'error': {'code': code, 'message': message}}


def add_arguments(parser):
    parser.add_argument('--enable-live', action='store_true',
                        help='operator opt-in: register the paid jev_decide tool (requires the flags below)')
    parser.add_argument('--live-provider', choices=capabilities.provider_names(),
                        help='the single provider jev_decide may call')
    parser.add_argument('--live-model', help='model for jev_decide; defaults to the provider pinned default')
    parser.add_argument('--openrouter-mode', choices=capabilities.OPENROUTER_MODES)
    parser.add_argument('--allow-unlisted-model', action='store_true')
    parser.add_argument('--max-live-requests', type=int, default=0,
                        help=f'paid request budget for this process (1-{MAX_LIVE_REQUESTS}); required with --enable-live')
    parser.add_argument('--timeout', type=float, default=30.0)
    parser.add_argument('--max-attempts', type=int, default=3)


def build_server(args):
    live_flags = args.live_provider or args.live_model or args.max_live_requests or args.openrouter_mode
    if not args.enable_live:
        if live_flags:
            raise UsageError('live options require --enable-live')
        return MCPServer()
    if not args.live_provider:
        raise UsageError('--enable-live requires --live-provider')
    client = DecisionClient(args.live_provider, args.live_model, openrouter_mode=args.openrouter_mode,
                            allow_unlisted_model=args.allow_unlisted_model, timeout=args.timeout,
                            max_attempts=args.max_attempts)
    return MCPServer(live_client=client, max_live_requests=args.max_live_requests)


def serve_from_args(args):
    server = build_server(args)
    sys.stderr.write('jev-workflow MCP server ready (' +
                     ('live tool enabled by operator' if server._live is not None else 'offline tools only') + ')\n')
    sys.stderr.flush()
    server.serve(sys.stdin.buffer, sys.stdout.buffer)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(prog='jev-workflow-mcp', description='stdio MCP server for jev-workflow')
    add_arguments(parser)
    args = parser.parse_args(argv)
    try:
        serve_from_args(args)
    except JevError as error:
        sys.stderr.write(f'jev-workflow-mcp: {error.code}: {error}\n')
        return error.exit_code
    return 0


if __name__ == '__main__':
    sys.exit(main())
