"""Minimal HTTPS transport: no redirects, no environment proxies, bounded reads.

Exceptions raised here carry fixed messages plus an exception class name only;
response bodies, URLs, headers and low-level error text are never included.
"""
from dataclasses import dataclass, field
import http.client
import socket
import ssl
import threading
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


_ACTIVE = threading.local()


def _track(factory):
    """Record each connection the opener creates so the attempt watchdog can close it."""
    def make(host, **kwargs):
        connection = factory(host, **kwargs)
        registry = getattr(_ACTIVE, 'connections', None)
        if registry is not None:
            registry.append(connection)
            connect = connection.connect

            def tracked_connect():
                connect()
                # urllib detaches conn.sock after the headers (Connection: close); keep
                # the socket itself so the watchdog can also interrupt body reads.
                registry.append(connection.sock)
            connection.connect = tracked_connect
        return connection
    return make


class _TrackedHTTPS(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_track(http.client.HTTPSConnection), req, context=self._context)


class _TrackedHTTP(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_track(http.client.HTTPConnection), req)


def build_opener():
    # Per-call opener: no process-global install_opener, empty proxy map
    # (HTTP(S)_PROXY / ALL_PROXY are ignored), redirect following disabled,
    # connections tracked for the overall attempt deadline. Endpoints are
    # restricted to HTTPS before this opener is used.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect(), _TrackedHTTPS(), _TrackedHTTP())


def _abort(connections, fired):
    fired.set()
    for connection in list(connections):
        sock = connection if isinstance(connection, socket.socket) else getattr(connection, 'sock', None)
        try:
            if sock is not None:
                sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            connection.close()
        except (OSError, http.client.HTTPException, AttributeError):
            pass


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
        connections, fired = [], threading.Event()
        watchdog = threading.Timer(timeout, _abort, args=(connections, fired))
        watchdog.daemon = True
        _ACTIVE.connections = connections
        watchdog.start()
        try:
            response = self._send(url, headers, body, timeout, time.monotonic() + timeout)
            if fired.is_set():
                raise TransportError('provider response exceeded the attempt timeout', code='outcome_unknown')
            return response
        except TransportError:
            if fired.is_set():
                raise TransportError('provider response exceeded the attempt timeout', code='outcome_unknown') from None
            raise
        finally:
            watchdog.cancel()
            _ACTIVE.connections = None

    def _send(self, url, headers, body, timeout, deadline):
        request = urllib.request.Request(url, data=body, headers=dict(headers), method='POST')
        try:
            with self._opener_factory().open(request, timeout=timeout) as response:
                raw = self._read_bounded(response, deadline)
                return HttpResponse(response.status, raw, _kept_headers(response.headers))
        except TransportError:
            raise
        except urllib.error.HTTPError as error:
            return self._error_response(error, deadline)
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
    def _error_response(error, deadline):
        # The error body is diagnostic only: bounded in size and by the attempt deadline.
        chunks, total, expired = [], 0, False
        reader = getattr(error, 'read1', None) or error.read
        try:
            while total < MAX_ERROR_BODY_BYTES:
                if time.monotonic() > deadline:
                    expired = True
                    break
                chunk = reader(min(4096, MAX_ERROR_BODY_BYTES - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
        except (OSError, http.client.HTTPException, ValueError):
            pass
        finally:
            try:
                error.close()
            except (OSError, http.client.HTTPException):
                pass
        if expired:
            raise TransportError('provider error response exceeded the attempt timeout', code='outcome_unknown')
        return HttpResponse(error.code, b''.join(chunks), _kept_headers(error.headers))
