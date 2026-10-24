"""Provider-selecting decision client.

``prepare`` and ``parse`` are offline. Only ``decide`` reads a credential and
contacts the provider's fixed HTTPS endpoint, and only for the provider chosen
at construction. There is no fallback to another provider, route or model.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
import random
import time

from . import VERSION, capabilities, credentials, providers
from .errors import CredentialError, ProviderError, ResponseError, TransportError, UsageError
from .model import DecisionRequest
from .transport import UrllibTransport

RESULT_SCHEMA = 'jev.result.v1'
DRY_RUN_SCHEMA = 'jev.dry_run.v1'
MAX_REQUEST_BYTES = 32 * 1024 * 1024
BACKOFF_BASE_SECONDS = 0.5
RETRY_AFTER_CAP_SECONDS = 30.0


@dataclass(frozen=True)
class PreparedCall:
    provider: str
    route: str
    model: str
    endpoint: str
    body_json: str
    header_items: tuple

    @property
    def body(self):
        return json.loads(self.body_json)

    @property
    def headers(self):
        return dict(self.header_items)

    @property
    def body_bytes(self):
        return self.body_json.encode('utf-8')

    def to_dict(self):
        headers = self.headers
        headers['Authorization'] = f'Bearer <read from {capabilities.credential_env(self.provider)} only at --live call time>'
        return {
            'schema_version': DRY_RUN_SCHEMA,
            'provider': self.provider,
            'route': self.route,
            'model': self.model,
            'endpoint': self.endpoint,
            'headers': headers,
            'body': self.body,
            'body_bytes': len(self.body_bytes),
            'network': 'not contacted',
            'credential': 'not read',
        }


@dataclass(frozen=True)
class DecisionResult:
    payload_json: str

    def to_dict(self):
        return json.loads(self.payload_json)

    @property
    def answers(self):
        return self.to_dict()['answers']


def _strict_loads(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result

    def constant(_name):
        raise ValueError('non-finite number')

    return json.loads(data, object_pairs_hook=unique, parse_constant=constant)


def _bounded(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
            or not low <= value <= high:
        raise UsageError(f'{name} must be between {low} and {high}')
    return value


class DecisionClient:
    def __init__(self, provider=None, model=None, *, openrouter_mode=None, experimental_images=False,
                 allow_unlisted_model=False, timeout=30.0, max_attempts=3, deadline=90.0,
                 environ=None, transport=None, sleep=None, clock=None):
        self.provider = provider or capabilities.DEFAULT_PROVIDER
        self._route_key = capabilities.route_key(self.provider, openrouter_mode)
        self.spec = capabilities.route_spec(self.provider, self._route_key)
        self.route = self.spec['route']
        self.model, self.model_caps = capabilities.resolve_model(
            self.provider, model, self._route_key, allow_unlisted=allow_unlisted_model)
        self.experimental_images = bool(experimental_images)
        self.timeout = _bounded(timeout, 1, 300, 'timeout')
        self.max_attempts = int(_bounded(max_attempts, 1, 5, 'max_attempts'))
        self.deadline = _bounded(deadline, 1, 900, 'deadline')
        self._environ = environ
        self._transport = transport or UrllibTransport()
        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic

    # ------------------------------------------------------------------ offline
    def prepare(self, request):
        if not isinstance(request, DecisionRequest):
            raise UsageError('prepare requires a parsed DecisionRequest')
        providers.check_request(request, self.spec, self.model, self.model_caps, self.experimental_images)
        body = providers.BUILDERS[self.route](request, self.model)
        body_json = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        if len(body_json.encode('utf-8')) > MAX_REQUEST_BYTES:
            raise UsageError('serialized request exceeds 32 MiB')
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
                   'User-Agent': f'jev-workflow/{VERSION}'}
        if self.route == 'typesafe.systemone' and (request.images or 'box' in request.question_types()):
            headers['TypeSafe-Danger-Zone-Images'] = 'true'
        return PreparedCall(self.provider, self.route, self.model, self.spec['endpoint'], body_json,
                            tuple(sorted(headers.items())))

    def parse(self, request, response, *, provenance=None):
        if not isinstance(request, DecisionRequest):
            raise UsageError('parse requires a parsed DecisionRequest')
        answers, reported, usage, extra = providers.parse(self.route, request, response, self.model_caps)
        if not capabilities.reported_model_ok(self.model, reported, self.model_caps):
            raise ResponseError('provider response rejected: reported model differs from the requested model')
        summary = {'answered': 0, 'refused': 0, 'not_applicable': 0}
        for answer in answers:
            summary[answer['status']] += 1
        details = {'client': 'jev-workflow', 'client_version': VERSION, 'endpoint': self.spec['endpoint'],
                   'contract_checked_on': capabilities.CHECKED_ON}
        details.update(extra)
        details.update(provenance or {})
        payload = {
            'schema_version': RESULT_SCHEMA,
            'provider': self.provider,
            'route': self.route,
            'model': {'requested': self.model, 'reported': reported},
            'answers': answers,
            'summary': summary,
            'usage': usage,
            'origin': dict(self.spec['origin']),
            'score_scale': self.spec['score_scale'],
            'provenance': details,
            'recommendation_only': True,
            'action_executed': False,
        }
        return DecisionResult(json.dumps(payload, ensure_ascii=False, allow_nan=False))

    # ------------------------------------------------------------------ live
    def secrets(self):
        """Values to redact from live-mode output (selected provider only)."""
        environ = os.environ if self._environ is None else self._environ
        value = environ.get(capabilities.credential_env(self.provider))
        return [value] if value else []

    def decide(self, request):
        """Send one paid request to the selected provider. Never falls back."""
        prepared = self.prepare(request)
        environ = os.environ if self._environ is None else self._environ
        key = credentials.read_api_key(self.provider, environ)
        if key in prepared.body_json:
            raise UsageError('request content contains the credential value; refusing to send it')
        headers = dict(prepared.headers, Authorization=f'Bearer {key}')
        body = prepared.body_bytes
        started = self._clock()
        attempt = 0
        while True:
            attempt += 1
            remaining = self.deadline - (self._clock() - started)
            if remaining <= 0:
                raise TransportError('retry deadline exhausted before a response', code='deadline_exhausted')
            try:
                response = self._transport.send(prepared.endpoint, headers, body, min(self.timeout, remaining))
            except TransportError as error:
                if error.retryable and self._may_retry(attempt, started, None):
                    continue
                raise TransportError(credentials.redact(str(error), [key]), code=error.code) from None
            status = response.status
            if status == 200:
                break
            if 300 <= status < 400:
                raise ProviderError(f'provider redirect (HTTP {status}) refused; credentials are never forwarded',
                                    code='redirect_refused', status=status)
            if status in (401, 403):
                raise CredentialError(f'provider rejected the credential or permission (HTTP {status})',
                                      code='credential_rejected', status=status)
            if status == 404 and self.route.startswith('openrouter.') and _allowed_providers_block(response.body):
                raise ProviderError('OpenRouter account routing policy blocked the selected provider '
                                    '(check Allowed Providers / data policy settings)',
                                    code='openrouter_provider_not_allowed', status=status)
            if status in self.spec['retry_statuses'] and self._may_retry(attempt, started, response.headers):
                continue
            raise ProviderError(f'provider request failed (HTTP {status})', status=status)
        try:
            text = response.body.decode('utf-8')
            document = _strict_loads(text)
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ResponseError('provider response rejected: body is not strict UTF-8 JSON') from None
        if key in text:
            raise ResponseError('provider response rejected: credential echo detected')
        result = self.parse(request, document, provenance={
            'request_sha256': hashlib.sha256(body).hexdigest(), 'attempts': attempt})
        return DecisionResult(credentials.redact(result.payload_json, [key]))

    def _may_retry(self, attempt, started, headers):
        if attempt >= self.max_attempts:
            return False
        wait = _retry_after(headers) if headers else None
        if wait is None:
            wait = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)) * (1 + random.random())
        if self._clock() - started + wait >= self.deadline:
            return False
        self._sleep(wait)
        return True


def _retry_after(headers):
    raw = headers.get('retry-after') if headers else None
    if not raw:
        return None
    try:
        seconds = float(raw.strip())
    except ValueError:
        return None
    if not math.isfinite(seconds) or seconds < 0:
        return None
    return min(seconds, RETRY_AFTER_CAP_SECONDS)


def _allowed_providers_block(body):
    try:
        payload = json.loads(body[:16384].decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return False
    error = payload.get('error') if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return False
    message = error.get('message')
    if isinstance(message, str) and ('allowed provider' in message.lower() or 'data policy' in message.lower()):
        return True
    metadata = error.get('metadata')
    return isinstance(metadata, dict) and metadata.get('failed_routing_step') == 'Filter by Allowed Providers'
