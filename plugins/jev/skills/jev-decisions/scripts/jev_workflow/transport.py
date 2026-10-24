"""Minimal HTTPS transport: no redirects, no environment proxies, bounded reads.

Exceptions raised here carry fixed messages plus an exception class name only;
response bodies, URLs, headers and low-level error text are never included.
"""
from dataclasses import dataclass, field
import http.client
import socket
import ssl
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
    for name in _KEPT_HEADERS:
        value = headers.get(name)
        if isinstance(value, str) and len(value) <= 64:
            kept[name] = value
    return kept


class UrllibTransport:
    def __init__(self, *, max_response_bytes=MAX_RESPONSE_BYTES, opener_factory=build_opener):
        self.max_response_bytes = max_response_bytes
        self._opener_factory = opener_factory

    def send(self, url, headers, body, timeout):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
            raise TransportError('refusing a non-HTTPS or credential-bearing URL', code='endpoint_refused')
        request = urllib.request.Request(url, data=body, headers=dict(headers), method='POST')
        try:
            with self._opener_factory().open(request, timeout=timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise TransportError('provider response exceeds the size limit', code='response_too_large')
                return HttpResponse(response.status, raw, _kept_headers(response.headers))
        except TransportError:
            raise
        except urllib.error.HTTPError as error:
            return self._error_response(error)
        except http.client.HTTPException as error:
            # Includes IncompleteRead/RemoteDisconnected/BadStatusLine: protocol
            # corruption may already have been billed, so it is not retried.
            raise TransportError(f'invalid HTTP response ({type(error).__name__})', code='http_protocol_error') from None
        except urllib.error.URLError as error:
            reason = error.reason
            if isinstance(reason, ssl.SSLError):
                raise TransportError(f'TLS failure ({type(reason).__name__})', code='tls_error') from None
            retryable = isinstance(reason, (socket.timeout, TimeoutError, ConnectionError, socket.gaierror, OSError))
            raise TransportError(f'connection failed ({type(reason).__name__})', retryable=retryable) from None
        except ssl.SSLError as error:
            raise TransportError(f'TLS failure ({type(error).__name__})', code='tls_error') from None
        except (socket.timeout, TimeoutError):
            raise TransportError('request timed out', retryable=True, code='timeout') from None
        except OSError as error:
            raise TransportError(f'connection failed ({type(error).__name__})', retryable=True) from None
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
