"""Error types with stable codes and exit statuses.

Messages are fixed, sanitized diagnostics. They never interpolate provider
response bodies, request content, credentials or transport exception text.
"""

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CREDENTIAL = 3
EXIT_PROVIDER = 4
EXIT_RESPONSE = 5
EXIT_CAPABILITY = 6


class JevError(Exception):
    code = 'jev_error'
    exit_code = EXIT_PROVIDER

    def __init__(self, message, *, code=None, status=None):
        super().__init__(message)
        if code:
            self.code = code
        self.status = status

    def to_dict(self):
        error = {'code': self.code, 'message': str(self)}
        if self.status is not None:
            error['http_status'] = self.status
        return {'schema_version': 'jev.error.v1', 'error': error, 'exit_code': self.exit_code}


class UsageError(JevError):
    """Invalid request, arguments or local input. Nothing was sent."""
    code = 'invalid_request'
    exit_code = EXIT_USAGE


class CapabilityError(JevError):
    """The selected provider/model/route cannot express the request. Nothing was sent."""
    code = 'unsupported_capability'
    exit_code = EXIT_CAPABILITY


class CredentialError(JevError):
    """Credential absent, malformed or rejected by the provider."""
    code = 'credential_error'
    exit_code = EXIT_CREDENTIAL


class ProviderError(JevError):
    """Provider returned a non-success HTTP status."""
    code = 'provider_http_error'
    exit_code = EXIT_PROVIDER


class TransportError(JevError):
    """Network, TLS, timeout or HTTP protocol failure."""
    code = 'transport_error'
    exit_code = EXIT_PROVIDER

    def __init__(self, message, *, retryable=False, code=None):
        super().__init__(message, code=code)
        self.retryable = retryable


class ResponseError(JevError):
    """Provider response violated the pinned contract; the result is discarded."""
    code = 'malformed_response'
    exit_code = EXIT_RESPONSE
