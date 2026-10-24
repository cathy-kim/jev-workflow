"""Synthetic fixtures for the multi-provider client tests.

Every value here is invented for offline tests. None of it is a recorded
provider response, measured usage, real customer data or a real credential.
"""
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'plugins' / 'jev' / 'skills' / 'jev-decisions'
SCRIPTS = SKILL / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# Obviously fake values that never match a real key format.
FAKE_KEYS = {
    'openai': 'synthetic-openai-key-0000',
    'typesafe': 'synthetic-typesafe-key-1111',
    'openrouter': 'synthetic-openrouter-key-2222',
}

REQUEST = {
    'schema_version': 'jev.request.v1',
    'state': 'Synthetic ticket: I was charged twice for one order.',
    'questions': [
        {'id': 'billing', 'type': 'noul', 'instructions': 'Is this message about billing?'},
        {'id': 'team', 'type': 'choice', 'instructions': 'Which team should own this ticket?',
         'options': [{'value': 'billing', 'description': 'Payments and refunds.'},
                     {'value': 'technical', 'description': 'Problems using the product.'},
                     {'value': 'other'}]},
        {'id': 'urgency', 'type': 'score', 'instructions': 'How urgent is this ticket?',
         'levels': [{'label': 'Can wait'}, {'label': 'This week'},
                    {'label': 'Today', 'description': 'Blocking work right now.'}]},
    ],
}

OPENAI_RESPONSE = {
    'answers': [
        {'type': 'predicate', 'name': 'billing', 'probability': 0.91},
        {'type': 'choice', 'name': 'team', 'choice': 'billing',
         'probabilities': [{'value': 'billing', 'probability': 0.9},
                           {'value': 'technical', 'probability': 0.06},
                           {'value': 'other', 'probability': 0.04}],
         'confidence': 0.85},
        {'type': 'score', 'name': 'urgency', 'score': 1.1,
         'probabilities': [{'value': 0, 'label': 'Can wait', 'probability': 0.1},
                           {'value': 1, 'label': 'This week', 'probability': 0.7},
                           {'value': 2, 'label': 'Today', 'probability': 0.2}],
         'confidence': 0.55},
    ],
    'model': 'gpt-6-luna',
    'usage': {'input_tokens': 120, 'input_tokens_details': {'cache_write_tokens': 0, 'cached_tokens': 0},
              'output_tokens': 9, 'output_tokens_details': {'reasoning_tokens': 0}, 'total_tokens': 129},
}

TYPESAFE_ANSWERS = {
    'billing': {'type': 'noul', 'noul': 0.93},
    'team': {'type': 'choice', 'choice': 'billing', 'confidence': 0.9,
             'probabilities': {'billing': 0.92, 'technical': 0.05, 'other': 0.03}},
    'urgency': {'type': 'score', 'score': 1.43, 'confidence': 0.35,
                'legend': {'0': 'Can wait', '1': 'This week',
                           '2': {'label': 'Today', 'description': 'Blocking work right now.'}},
                'probabilities': {'0': 0.0, '1': 0.57, '2': 0.43}},
}

TYPESAFE_RESPONSE = {'model': 'jev-1.14.0', 'answers': TYPESAFE_ANSWERS,
                     'usage': {'input_tokens': 140, 'output_tokens': 12}}

OPENROUTER_DECISIONS_RESPONSE = {
    'answers': TYPESAFE_ANSWERS,
    'id': 'gen-dec-synthetic-0001',
    'model': 'typesafe/jev-1.14-20261014',
    'provider': 'TypeSafe',
    'usage': {'cost': 0.00002, 'input_tokens': 140, 'output_tokens': 12},
}

STRUCTURED_CONTENT = {
    'answers': {
        'billing': {'status': 'answered', 'probability': 0.8},
        'team': {'status': 'answered', 'choice': 'billing',
                 'probabilities': {'billing': 0.7, 'technical': 0.2, 'other': 0.1}},
        'urgency': {'status': 'not_applicable', 'level_probabilities': None},
    }
}


def structured_response(content=None, *, model='example/judge-model', finish='stop', refusal=None):
    body = STRUCTURED_CONTENT if content is None else content
    return {
        'id': 'gen-synthetic-0002',
        'model': model,
        'choices': [{'index': 0, 'finish_reason': finish,
                     'message': {'role': 'assistant',
                                 'content': body if isinstance(body, str) else json.dumps(body),
                                 'refusal': refusal}}],
        'usage': {'prompt_tokens': 300, 'completion_tokens': 80, 'total_tokens': 380},
    }


def fresh(value):
    return copy.deepcopy(value)


def _png_1x1():
    """Build a valid 1x1 RGBA PNG in memory; synthetic pixel, not user data."""
    import struct
    import zlib

    def chunk(kind, data):
        return (struct.pack('>I', len(data)) + kind + data
                + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))

    header = struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)
    pixels = zlib.compress(b'\x00\x00\x00\x00\x00')
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', pixels) + chunk(b'IEND', b'')


PNG_1X1 = _png_1x1()
