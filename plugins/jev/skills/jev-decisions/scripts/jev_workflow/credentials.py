"""Credential access: one environment variable per provider, read at call time.

No dotenv files, keychains, password managers, config files or command-line
arguments are consulted. Values are never logged or returned in output.
"""
from . import capabilities
from .errors import CredentialError

REDACTED = '[REDACTED]'


def read_api_key(provider, environ):
    name = capabilities.credential_env(provider)
    value = environ.get(name)
    if not value:
        raise CredentialError(f'{name} is not set in this process environment; no other credential source is read',
                              code='credential_missing')
    if not 8 <= len(value) <= 4096 or any(not 0x21 <= ord(c) <= 0x7e for c in value):
        raise CredentialError(f'{name} has an invalid format (expected printable ASCII without whitespace)',
                              code='credential_invalid')
    return value


def redact(text, secrets):
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, REDACTED)
    return text
