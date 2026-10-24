"""Provider-neutral immutable decision request.

A request is shared ``state`` plus an ordered list of typed questions:

* ``noul`` (alias ``predicate``): probability that a statement is true.
* ``choice``: one of 2-255 typed option values (string or boolean).
* ``score``: expected 0-based index over 2-10 ordered levels.
* ``box``: image localization (TypeSafe direct, experimental, Jev 1.14 only).

Validation is strict: unknown fields, duplicates, empty identifiers, non-finite
numbers and out-of-range counts are rejected instead of repaired.
"""
import base64
import binascii
from dataclasses import dataclass
import json
import re
import struct
from typing import NoReturn

from .errors import UsageError

REQUEST_SCHEMA = 'jev.request.v1'
QUESTION_TYPES = ('noul', 'choice', 'score', 'box')
TYPE_ALIASES = {'predicate': 'noul'}
ID_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')
IMAGE_REF_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')

MAX_QUESTIONS = 400
MIN_CHOICES, MAX_CHOICES = 2, 255
MIN_LEVELS, MAX_LEVELS = 2, 10
MAX_INSTRUCTIONS_CHARS = 32_000
MAX_DESCRIPTION_CHARS = 8_000
MAX_LABEL_CHARS = 2_000
MAX_OPTION_CHARS = 1_000
MAX_STATE_BYTES = 4 * 1024 * 1024
MAX_STATE_DEPTH = 64
MAX_IMAGES = 16
MAX_IMAGE_BYTES = 16 * 1024 * 1024

_REQUEST_FIELDS = {'schema_version', 'state', 'questions', 'images'}
_QUESTION_FIELDS = {
    'noul': {'id', 'type', 'instructions', 'criteria'},
    'choice': {'id', 'type', 'instructions', 'options'},
    'score': {'id', 'type', 'instructions', 'levels'},
    'box': {'id', 'type', 'instructions'},
}
_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
_JPEG_MAGIC = b'\xff\xd8\xff'


@dataclass(frozen=True)
class Option:
    value: object  # str or bool; typed, so 'true' and True are distinct
    description: object = None


@dataclass(frozen=True)
class Level:
    label: str
    description: object = None


@dataclass(frozen=True)
class Question:
    id: str
    type: str
    instructions: str
    criteria_true: object = None
    criteria_false: object = None
    options: tuple = ()
    levels: tuple = ()

    @property
    def has_criteria(self):
        return self.criteria_true is not None


@dataclass(frozen=True)
class Image:
    ref: str
    format: str  # 'png' or 'jpg'
    data_base64: str
    size: int


@dataclass(frozen=True)
class DecisionRequest:
    state_json: str
    questions: tuple
    images: tuple = ()

    @property
    def state(self):
        """A fresh copy, so callers cannot mutate the request."""
        return json.loads(self.state_json)

    @property
    def state_is_text(self):
        return self.state_json.startswith('"')

    def question_types(self):
        return {q.type for q in self.questions}


def option_key(value):
    """Type-aware identity: the string 'true' and boolean True never collide."""
    return (type(value).__name__, value)


def _fail(message) -> NoReturn:
    raise UsageError(message)


def _text(value, field, limit):
    if not isinstance(value, str):
        _fail(f'{field} must be a string')
    if not value.strip():
        _fail(f'{field} must not be empty')
    if len(value) > limit:
        _fail(f'{field} exceeds {limit} characters')
    return value


def _optional_text(value, field, limit):
    return None if value is None else _text(value, field, limit)


def _check_fields(obj, allowed, where):
    if not isinstance(obj, dict):
        _fail(f'{where} must be an object')
    unknown = sorted(set(obj) - allowed)
    if unknown:
        _fail(f'{where} has unknown field(s): {", ".join(unknown)}')


def _check_state_value(value, depth):
    if depth > MAX_STATE_DEPTH:
        _fail(f'state nesting exceeds {MAX_STATE_DEPTH} levels')
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if value != value or value in (float('inf'), float('-inf')):
            _fail('state must contain only finite JSON numbers')
        return
    if isinstance(value, list):
        for item in value:
            _check_state_value(item, depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail('state object keys must be strings')
            _check_state_value(item, depth + 1)
        return
    _fail('state contains a value that is not JSON')


def _state_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _state_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _state_strings(item)


def _parse_state(state):
    if not isinstance(state, (str, dict, list)):
        _fail('state must be a string, object or array')
    if isinstance(state, str) and not state.strip():
        _fail('state must not be empty')
    _check_state_value(state, 0)
    try:
        text = json.dumps(state, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    except (ValueError, TypeError, RecursionError):
        _fail('state must contain only finite JSON values')
    if len(text.encode('utf-8')) > MAX_STATE_BYTES:
        _fail(f'state exceeds {MAX_STATE_BYTES} bytes')
    return text


def _parse_question(raw, index):
    where = f'questions[{index}]'
    if not isinstance(raw, dict):
        _fail(f'{where} must be an object')
    kind = raw.get('type')
    kind = TYPE_ALIASES.get(kind, kind)
    if kind not in QUESTION_TYPES:
        _fail(f'{where}.type must be one of noul, predicate, choice, score, box')
    _check_fields(raw, _QUESTION_FIELDS[kind], where)
    qid = raw.get('id')
    if not isinstance(qid, str) or not ID_PATTERN.match(qid):
        _fail(f'{where}.id must match {ID_PATTERN.pattern}')
    instructions = _text(raw.get('instructions'), f'{where}.instructions', MAX_INSTRUCTIONS_CHARS)
    if kind == 'noul':
        criteria = raw.get('criteria')
        if criteria is None:
            return Question(qid, kind, instructions)
        if not isinstance(criteria, dict) or set(criteria) != {'true', 'false'}:
            _fail(f"{where}.criteria requires both 'true' and 'false' strings")
        return Question(qid, kind, instructions,
                        criteria_true=_text(criteria['true'], f'{where}.criteria.true', MAX_DESCRIPTION_CHARS),
                        criteria_false=_text(criteria['false'], f'{where}.criteria.false', MAX_DESCRIPTION_CHARS))
    if kind == 'choice':
        options = raw.get('options')
        if not isinstance(options, list) or not MIN_CHOICES <= len(options) <= MAX_CHOICES:
            _fail(f'{where}.options requires {MIN_CHOICES}-{MAX_CHOICES} choices')
        parsed, seen = [], set()
        for position, option in enumerate(options):
            owhere = f'{where}.options[{position}]'
            _check_fields(option, {'value', 'description'}, owhere)
            value = option.get('value')
            if isinstance(value, str):
                _text(value, f'{owhere}.value', MAX_OPTION_CHARS)
            elif not isinstance(value, bool):
                _fail(f'{owhere}.value must be a string or boolean')
            key = option_key(value)
            if key in seen:
                _fail(f'{where}.options values must be distinct (typed)')
            seen.add(key)
            parsed.append(Option(value, _optional_text(option.get('description'), f'{owhere}.description',
                                                       MAX_DESCRIPTION_CHARS)))
        return Question(qid, kind, instructions, options=tuple(parsed))
    if kind == 'score':
        levels = raw.get('levels')
        if not isinstance(levels, list) or not MIN_LEVELS <= len(levels) <= MAX_LEVELS:
            _fail(f'{where}.levels requires {MIN_LEVELS}-{MAX_LEVELS} ordered levels')
        parsed = []
        for position, level in enumerate(levels):
            lwhere = f'{where}.levels[{position}]'
            _check_fields(level, {'label', 'description'}, lwhere)
            parsed.append(Level(_text(level.get('label'), f'{lwhere}.label', MAX_LABEL_CHARS),
                                _optional_text(level.get('description'), f'{lwhere}.description',
                                               MAX_DESCRIPTION_CHARS)))
        if len({level.label for level in parsed}) != len(parsed):
            _fail(f'{where}.levels labels must be distinct')
        return Question(qid, kind, instructions, levels=tuple(parsed))
    return Question(qid, kind, instructions)


def _png_is_still(data):
    position = len(_PNG_MAGIC)
    while position + 8 <= len(data):
        length, kind = struct.unpack('>I4s', data[position:position + 8])
        if kind == b'acTL':
            return False
        if kind in (b'IDAT', b'IEND'):
            return True
        position += 12 + length
    return False


def _parse_image(raw, index, state_strings):
    where = f'images[{index}]'
    _check_fields(raw, {'ref', 'format', 'data_base64'}, where)
    ref = raw.get('ref')
    if not isinstance(ref, str) or not IMAGE_REF_PATTERN.match(ref):
        _fail(f'{where}.ref must match {IMAGE_REF_PATTERN.pattern}')
    if not any(ref in text for text in state_strings):
        _fail(f'{where}.ref must appear inside state so the image has a position')
    fmt = raw.get('format')
    fmt = {'jpeg': 'jpg'}.get(fmt, fmt)
    if fmt not in ('png', 'jpg'):
        _fail(f'{where}.format must be png or jpeg')
    encoded = raw.get('data_base64')
    if not isinstance(encoded, str) or not encoded:
        _fail(f'{where}.data_base64 must be a non-empty base64 string')
    if len(encoded) > (MAX_IMAGE_BYTES // 3 + 2) * 4:
        _fail(f'{where} exceeds {MAX_IMAGE_BYTES} bytes')
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        _fail(f'{where}.data_base64 is not valid base64')
    if not data or len(data) > MAX_IMAGE_BYTES:
        _fail(f'{where} must be 1-{MAX_IMAGE_BYTES} bytes after decoding')
    if fmt == 'png' and not (data.startswith(_PNG_MAGIC) and _png_is_still(data)):
        _fail(f'{where} is not a still PNG image')
    if fmt == 'jpg' and not data.startswith(_JPEG_MAGIC):
        _fail(f'{where} is not a JPEG image')
    return Image(ref, fmt, encoded, len(data))


def parse_request(raw):
    """Validate a JSON-compatible object and return an immutable request."""
    _check_fields(raw, _REQUEST_FIELDS, 'request')
    if 'schema_version' in raw and raw['schema_version'] != REQUEST_SCHEMA:
        _fail(f'schema_version must be {REQUEST_SCHEMA}')
    if 'state' not in raw:
        _fail('request.state is required')
    state_json = _parse_state(raw['state'])
    questions = raw.get('questions')
    if not isinstance(questions, list) or not 1 <= len(questions) <= MAX_QUESTIONS:
        _fail(f'questions must be a list of 1-{MAX_QUESTIONS} questions')
    parsed = tuple(_parse_question(question, index) for index, question in enumerate(questions))
    ids = [question.id for question in parsed]
    if len(set(ids)) != len(ids):
        _fail('question ids must be unique; duplicate id found')
    images = raw.get('images', [])
    if not isinstance(images, list) or len(images) > MAX_IMAGES:
        _fail(f'images must be a list of at most {MAX_IMAGES} images')
    strings = list(_state_strings(json.loads(state_json))) if images else []
    parsed_images = tuple(_parse_image(image, index, strings) for index, image in enumerate(images))
    refs = [image.ref for image in parsed_images]
    if len(set(refs)) != len(refs):
        _fail('image refs must be unique')
    return DecisionRequest(state_json, parsed, parsed_images)


def load_request_text(text):
    """Parse JSON text strictly (duplicate keys and NaN/Infinity rejected)."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _fail('request JSON contains a duplicate key')
            result[key] = value
        return result

    def constant(name):
        _fail(f'request JSON contains non-finite number {name}')

    try:
        raw = json.loads(text, object_pairs_hook=unique, parse_constant=constant)
    except UsageError:
        raise
    except (ValueError, RecursionError):
        _fail('request is not valid JSON')
    return parse_request(raw)
