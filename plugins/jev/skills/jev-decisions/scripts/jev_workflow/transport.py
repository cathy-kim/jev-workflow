"""Minimal HTTPS transport: no redirects, no environment proxies, bounded reads.

Exceptions raised here carry fixed messages plus an exception class name only;
response bodies, URLs, headers and low-level error text are never included.
"""
from dataclasses import dataclass, field
import http.client
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from .errors import TransportError

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_ERROR_BODY_BYTES = 16 * 1024
_KEPT_HEADERS = ('retry-after',)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes = b''
    headers: dict = field(default_factory=dict)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Return redirects to the caller as ordinary statuses; credentials never follow them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def build_opener():
    # Per-call opener: no process-global install_opener, empty proxy map
    # (HTTP(S)_PROXY / ALL_PROXY are ignored), redirect following disabled.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def _kept_headers(headers):
    kept = {}
    if headers is None:
        return kept
    try:
        items = list(headers.items())
    except (AttributeError, TypeError):
        return kept
    for name, value in items:
        lowered = name.lower() if isinstance(name, str) else ''
        if lowered in _KEPT_HEADERS and isinstance(value, str) and len(value) <= 64:
            kept[lowered] = value
    return kept


def _allowed_url(url):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == 'https' and bool(parts.hostname) and not parts.username and not parts.password


class UrllibTransport:
    """Errors raised before the request is fully sent are retryable; anything after
    the body was sent (read timeouts, resets, protocol corruption) is reported as
    ``outcome_unknown`` and never replayed, because the provider may have billed it."""

    def __init__(self, *, max_response_bytes=MAX_RESPONSE_BYTES, opener_factory=build_opener):
        self.max_response_bytes = max_response_bytes
        self._opener_factory = opener_factory

    def _read_bounded(self, response, deadline):
        reader = getattr(response, 'read1', None) or response.read
        chunks, total = [], 0
        while True:
            if time.monotonic() > deadline:
                raise TransportError('provider response exceeded the attempt timeout', code='outcome_unknown')
            chunk = reader(65536)
            if not chunk:
                return b''.join(chunks)
            total += len(chunk)
            if total > self.max_response_bytes:
                raise TransportError('provider response exceeds the size limit', code='response_too_large')
            chunks.append(chunk)

    def send(self, url, headers, body, timeout):
        if not _allowed_url(url):
            raise TransportError('refusing a non-HTTPS or credential-bearing URL', code='endpoint_refused')
        deadline = time.monotonic() + timeout
        request = urllib.request.Request(url, data=body, headers=dict(headers), method='POST')
        try:
            with self._opener_factory().open(request, timeout=timeout) as response:
                raw = self._read_bounded(response, deadline)
                return HttpResponse(response.status, raw, _kept_headers(response.headers))
        except TransportError:
            raise
        except urllib.error.HTTPError as error:
            return self._error_response(error)
        except urllib.error.URLError as error:
            # urllib raises URLError only around connect/send, before any response:
            # DNS failure, refused connection, connect timeout.
            reason = error.reason
            if isinstance(reason, ssl.SSLError):
                raise TransportError(f'TLS failure ({type(reason).__name__})', code='tls_error') from None
            raise TransportError(f'connection failed before a response ({type(reason).__name__})',
                                 retryable=True, code='connection_failed') from None
        except http.client.HTTPException as error:
            raise TransportError(f'invalid HTTP response; outcome unknown ({type(error).__name__})',
                                 code='outcome_unknown') from None
        except ssl.SSLError as error:
            raise TransportError(f'TLS failure; outcome unknown ({type(error).__name__})', code='outcome_unknown') from None
        except OSError as error:
            # Includes TimeoutError and ConnectionResetError after the body was sent.
            raise TransportError(f'no complete response; outcome unknown ({type(error).__name__})',
                                 code='outcome_unknown') from None
        except ValueError as error:
            raise TransportError(f'request could not be sent ({type(error).__name__})') from None

    @staticmethod
    def _error_response(error):
        body = b''
        try:
            body = error.read(MAX_ERROR_BODY_BYTES) or b''
        except (OSError, http.client.HTTPException, ValueError):
            body = b''
        finally:
            try:
                error.close()
            except (OSError, http.client.HTTPException):
                pass
        return HttpResponse(error.code, body, _kept_headers(error.headers))
