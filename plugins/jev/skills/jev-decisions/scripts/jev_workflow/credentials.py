"""Credential access: one environment variable per provider, read at call time.

No dotenv files, keychains, password managers, config files or command-line
arguments are consulted. Values are never logged or returned in output.
"""
import json

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
        if not secret or len(secret) < 4:
            continue
        # Also the JSON-escaped spelling, in case the value contains quotes or backslashes.
        for form in {secret, json.dumps(secret)[1:-1], json.dumps(secret, ensure_ascii=False)[1:-1]}:
            text = text.replace(form, REDACTED)
    return text
