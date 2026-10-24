"""jev-workflow command line.

stdout carries exactly one JSON document (result, preview or error);
stderr carries a one-line diagnostic on failure. Only ``decide --live`` and
``ask --live`` read a credential or contact a provider.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import platform
import sys

from . import VERSION, capabilities
from .client import DecisionClient
from .errors import EXIT_OK, JevError, ResponseError, UsageError
from .model import load_request_text, strict_json_loads

PROG = 'jev-workflow'
MAX_INPUT_BYTES = 48 * 1024 * 1024
MAX_IMAGE_FILE_BYTES = 16 * 1024 * 1024


def _read_input(value, label):
    if value == '-':
        data = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    else:
        path = Path(value)
        try:
            if not path.is_file():
                raise UsageError(f'{label} must be an existing regular file or - for stdin')
            with path.open('rb') as handle:
                data = handle.read(MAX_INPUT_BYTES + 1)
        except OSError as error:
            raise UsageError(f'{label} could not be read ({type(error).__name__})') from None
    if len(data) > MAX_INPUT_BYTES:
        raise UsageError(f'{label} exceeds {MAX_INPUT_BYTES} bytes')
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        raise UsageError(f'{label} must be UTF-8 JSON') from None


def _image_entry(spec):
    ref, sep, path_text = spec.partition('=')
    if not sep or not ref or not path_text:
        raise UsageError('--image expects REF=PATH')
    path = Path(path_text)
    try:
        if not path.is_file():
            raise UsageError('--image path must be an existing regular file')
        with path.open('rb') as handle:
            data = handle.read(MAX_IMAGE_FILE_BYTES + 1)
    except OSError as error:
        raise UsageError(f'--image could not be read ({type(error).__name__})') from None
    if len(data) > MAX_IMAGE_FILE_BYTES:
        raise UsageError('--image exceeds 16 MiB')
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        fmt = 'png'
    elif data.startswith(b'\xff\xd8\xff'):
        fmt = 'jpeg'
    else:
        raise UsageError('--image must be a PNG or JPEG file')
    return {'ref': ref, 'format': fmt, 'data_base64': base64.b64encode(data).decode('ascii')}


def _provider_choice(args):
    if args.provider:
        return args.provider, 'flag'
    env_value = os.environ.get('JEV_PROVIDER')
    if env_value:
        if env_value not in capabilities.provider_names():
            raise UsageError('JEV_PROVIDER must be openai, typesafe or openrouter')
        return env_value, 'env:JEV_PROVIDER'
    return capabilities.DEFAULT_PROVIDER, 'default'


def _client(args):
    provider, source = _provider_choice(args)
    client = DecisionClient(provider, args.model, openrouter_mode=args.openrouter_mode,
                            experimental_images=args.experimental_images,
                            allow_unlisted_model=args.allow_unlisted_model,
                            timeout=args.timeout, max_attempts=args.max_attempts)
    return client, {'provider_source': source,
                    'model_source': 'flag' if args.model else 'provider_default'}


def _load_request(args, raw_text=None):
    text = raw_text if raw_text is not None else _read_input(args.request, '--request')
    if not args.image:
        return load_request_text(text)
    try:
        raw = strict_json_loads(text)
    except (ValueError, RecursionError):
        raise UsageError('request is not strict JSON') from None
    if not isinstance(raw, dict):
        raise UsageError('request must be an object')
    raw = dict(raw)
    raw['images'] = list(raw.get('images') or []) + [_image_entry(spec) for spec in args.image]
    return load_request_text(json.dumps(raw))


def _preview(client, request, config):
    preview = client.prepare(request).to_dict()
    preview['config'] = config
    preview['valid'] = True
    return preview


def _run_request(args, request):
    client, config = _client(args)
    if args.live:
        result = client.decide(request).to_dict()
        result['config'] = config
        return result
    return _preview(client, request, config)


def cmd_providers(_args):
    return capabilities.matrix()


def cmd_capabilities(args):
    provider, source = _provider_choice(args)
    route = capabilities.route_key(provider, args.openrouter_mode)
    spec = capabilities.route_spec(provider, route)
    model, caps = capabilities.resolve_model(provider, args.model, route, allow_unlisted=args.allow_unlisted_model)
    caps.pop('alias_pattern', None)
    route_caps = {k: v for k, v in spec.items() if k != 'models'}
    return {'schema_version': 'jev.capabilities.v1', 'provider': provider, 'provider_source': source,
            'credential_env': capabilities.credential_env(provider), 'model': model,
            'model_capabilities': caps, 'route': route_caps}


def cmd_doctor(_args):
    return {
        'schema_version': 'jev.doctor.v1',
        'version': VERSION,
        'python': platform.python_version(),
        'python_supported': sys.version_info >= (3, 10),
        'default_provider': capabilities.DEFAULT_PROVIDER,
        'providers': list(capabilities.provider_names()),
        'credential_env': {name: capabilities.credential_env(name) for name in capabilities.provider_names()},
        'network': 'not contacted',
        'credentials': 'not inspected',
        'live_calls': 'only `decide --live` / `ask --live`, or an MCP server started with --enable-live',
    }


def cmd_validate(args):
    return _preview(*_client_and_request(args))


def _client_and_request(args):
    request = _load_request(args)
    client, config = _client(args)
    return client, request, config


def cmd_decide(args):
    return _run_request(args, _load_request(args))


def cmd_parse(args):
    request = _load_request(args)
    client, config = _client(args)
    text = _read_input(args.response, '--response')
    try:
        document = strict_json_loads(text)
    except (ValueError, RecursionError):
        raise ResponseError('saved response is not strict JSON (duplicate keys and NaN/Infinity are rejected)') from None
    result = client.parse(request, document, provenance={'source': 'saved response (offline parse)'}).to_dict()
    result['config'] = config
    return result


def cmd_ask(args):
    if not args.items:
        raise UsageError('ask needs at least one --noul, --choice or --score')
    if args.state is None and args.state_file is None:
        raise UsageError('ask needs --state TEXT or --state-file PATH|-')
    if args.state is not None and args.state_file is not None:
        raise UsageError('use either --state or --state-file')
    state = args.state if args.state is not None else _read_input(args.state_file, '--state-file')
    questions = []
    for kind, text in args.items:
        if kind in ('noul', 'choice', 'score'):
            question = {'id': f'q{len(questions) + 1}', 'type': kind, 'instructions': text}
            if kind == 'choice':
                question['options'] = []
            if kind == 'score':
                question['levels'] = []
            questions.append(question)
            continue
        target = 'choice' if kind == 'option' else 'score'
        if not questions or questions[-1]['type'] != target:
            raise UsageError(f'--{kind} must follow a --{target} question')
        value, sep, description = text.partition('=')
        entry = {'value' if kind == 'option' else 'label': value}
        if sep and description:
            entry['description'] = description
        questions[-1]['options' if kind == 'option' else 'levels'].append(entry)
    raw = json.dumps({'schema_version': 'jev.request.v1', 'state': state, 'questions': questions})
    args.request = None
    return _run_request(args, _load_request(args, raw_text=raw))


def cmd_install(args):
    from . import installer
    return installer.install(args.runtime, args.target, dry_run=args.dry_run, backup=args.backup)


def cmd_uninstall(args):
    from . import installer
    return installer.uninstall(args.target, dry_run=args.dry_run)


def cmd_mcp_serve(args):
    from . import mcp_server
    try:
        return mcp_server.serve_from_args(args)
    except JevError as error:
        # stdout is reserved for JSON-RPC; startup failures go to stderr only.
        sys.stderr.write(f'{PROG}: {error.code}: {error}\n')
        raise SystemExit(error.exit_code) from None


class _Ordered(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        items = list(getattr(namespace, self.dest) or [])
        items.append((option_string.lstrip('-'), values))
        setattr(namespace, self.dest, items)


def _provider_options(parser, *, live=False, request=True):
    parser.add_argument('--provider', choices=capabilities.provider_names(),
                        help='openai | typesafe | openrouter (precedence: flag > JEV_PROVIDER > openrouter)')
    parser.add_argument('--model', help='model id; default is pinned per provider (structured route requires it)')
    parser.add_argument('--openrouter-mode', choices=capabilities.OPENROUTER_MODES,
                        help='openrouter route: decisions (default, native decision model) or structured '
                             '(general LLM JSON judge, uncalibrated)')
    parser.add_argument('--allow-unlisted-model', action='store_true',
                        help='accept a model missing from the capability table with base capabilities')
    parser.add_argument('--experimental-images', action='store_true',
                        help='opt in to experimental TypeSafe images/Box (adds the documented header)')
    parser.add_argument('--image', action='append', default=[], metavar='REF=PATH',
                        help='attach a local PNG/JPEG under a ref that appears in state (explicit path only)')
    parser.add_argument('--timeout', type=float, default=30.0, help='per-attempt timeout seconds (1-300)')
    parser.add_argument('--max-attempts', type=int, default=3, help='attempts for documented transient errors (1-5)')
    if request:
        parser.add_argument('--request', required=True, metavar='PATH|-', help='request JSON file or - for stdin')
    if live:
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument('--dry-run', action='store_true', help='build and print the provider payload offline')
        mode.add_argument('--live', action='store_true', help='send one paid request to the selected provider')


def build_parser():
    parser = argparse.ArgumentParser(prog=PROG, description='Portable multi-provider typed decision client. '
                                     'Offline unless --live is given.')
    parser.add_argument('--version', action='version', version=f'{PROG} {VERSION}')
    parser.add_argument('--compact', action='store_true', help='single-line JSON output')
    sub = parser.add_subparsers(dest='command', required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--compact', action='store_true', default=argparse.SUPPRESS, help='single-line JSON output')

    p = sub.add_parser('providers', parents=[common], help='list providers, routes and capabilities (offline)')
    p.set_defaults(func=cmd_providers)

    p = sub.add_parser('capabilities', parents=[common], help='capabilities for one provider/model (offline)')
    _provider_options(p, request=False)
    p.set_defaults(func=cmd_capabilities)

    p = sub.add_parser('doctor', parents=[common], help='static environment check; no network, no credential inspection')
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser('validate', parents=[common], help='validate a request and print the provider payload (offline)')
    _provider_options(p)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser('decide', parents=[common], help='run a request file: --dry-run (offline) or --live (paid)')
    _provider_options(p, live=True)
    p.set_defaults(func=cmd_decide)

    p = sub.add_parser('ask', parents=[common], help='build a request from flags: --dry-run (offline) or --live (paid)')
    _provider_options(p, live=True, request=False)
    p.add_argument('--state', help='state text')
    p.add_argument('--state-file', metavar='PATH|-', help='state text file or - for stdin')
    for flag, help_text in (('--noul', 'probability question'), ('--choice', 'choice question'),
                            ('--option', 'VALUE[=DESCRIPTION] for the preceding --choice'),
                            ('--score', 'score question'), ('--level', 'LABEL[=DESCRIPTION] for the preceding --score')):
        p.add_argument(flag, dest='items', action=_Ordered, help=help_text)
    p.set_defaults(func=cmd_ask, items=[])

    p = sub.add_parser('parse', parents=[common], help='normalize a saved provider response against its request (offline)')
    _provider_options(p)
    p.add_argument('--response', required=True, metavar='PATH|-', help='saved provider response JSON')
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser('install', parents=[common], help='install the portable skill into an explicit skills directory')
    p.add_argument('--runtime', required=True, choices=('claude', 'codex', 'hermes', 'generic'))
    p.add_argument('--target', required=True, help='skills directory to install into (never defaulted)')
    p.add_argument('--dry-run', action='store_true', help='print the plan without writing')
    p.add_argument('--backup', action='store_true', help='move an existing different copy aside instead of refusing')
    p.set_defaults(func=cmd_install)

    p = sub.add_parser('uninstall', parents=[common], help='remove an install made by this tool and restore its backup')
    p.add_argument('--target', required=True, help='skills directory used for install')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser('mcp-serve', parents=[common], help='run the stdio MCP server (offline tools unless --enable-live)')
    from .mcp_server import add_arguments
    add_arguments(p)
    p.set_defaults(func=cmd_mcp_serve)
    return parser


def _emit(document, compact):
    if document is None:
        return
    text = json.dumps(document, ensure_ascii=False, allow_nan=False,
                      indent=None if compact else 2, separators=(',', ':') if compact else None)
    sys.stdout.write(text + '\n')


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        document = args.func(args)
    except JevError as error:
        _emit(error.to_dict(), getattr(args, 'compact', False))
        sys.stderr.write(f'{PROG}: {error.code}: {error}\n')
        return error.exit_code
    except KeyboardInterrupt:
        sys.stderr.write(f'{PROG}: interrupted\n')
        return 130
    except Exception as error:  # noqa: BLE001 - never print tracebacks that may contain data
        sys.stderr.write(f'{PROG}: internal_error ({type(error).__name__})\n')
        return 1
    _emit(document, args.compact)
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
