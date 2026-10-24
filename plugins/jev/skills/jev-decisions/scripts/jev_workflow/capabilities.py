"""Static, offline provider capability matrix.

Sources were read on 2026-10-24 (see references/live-client.md). The matrix
separates what a provider documents from what this client implements: a
feature the provider supports but this client does not serialize is reported
as unsupported and fails before any transport.
"""
import copy
import re

from .errors import CapabilityError, UsageError

DEFAULT_PROVIDER = 'openrouter'
OPENROUTER_MODES = ('decisions', 'structured')
CHECKED_ON = '2026-10-24'

_DECISION_ORIGIN = {
    'values': 'provider_decision_model',
    'confidence': 'provider_reported',
    'calibration': 'provider_claim_not_verified_by_client',
}

PROVIDERS = {
    'openai': {
        'credential_env': 'OPENAI_API_KEY',
        'default_route': 'decisions',
        'routes': {
            'decisions': {
                'route': 'openai.decisions',
                'endpoint': 'https://api.openai.com/v1/decisions',
                'default_model': 'gpt-6-luna',
                'models': {'gpt-6-luna': {'match': 'snapshot', 'images': False, 'box': False}},
                'question_types': ['noul', 'choice', 'score'],
                'provider_question_names': {'noul': 'predicate', 'choice': 'choice', 'score': 'score'},
                'noul_criteria': False,
                'boolean_choice_values': True,
                'refusal_answers': True,
                'state_shapes': ['string', 'object', 'array_of_objects'],
                'images': {'provider_documents': True, 'client_implements': False},
                'box': {'provider_documents': False, 'client_implements': False},
                'limits': {'questions': [1, 400], 'choices': [2, 255], 'levels': [2, 10],
                           'input_json_bytes': 262_144, 'input_json_depth': 32, 'input_json_values': 10_000},
                'retry_statuses': [429, 503],
                'origin': dict(_DECISION_ORIGIN),
                'score_scale': 'expected_level_index_0_to_n_minus_1',
            },
        },
    },
    'typesafe': {
        'credential_env': 'TYPESAFE_API_KEY',
        'default_route': 'systemone',
        'routes': {
            'systemone': {
                'route': 'typesafe.systemone',
                'endpoint': 'https://api.typesafe.ai/v1/systemone',
                'default_model': 'jev-1.14.0',
                'models': {
                    'jev-1.14.0': {'match': 'exact', 'images': True, 'box': True},
                    'jev-1.13.0': {'match': 'exact', 'images': True, 'box': False},
                    'jev-latest': {'match': 'alias', 'alias_pattern': r'^jev-\d+\.\d+\.\d+$',
                                   'images': True, 'box': False},
                    'jev-preview': {'match': 'alias', 'alias_pattern': r'^jev-\d+\.\d+\.\d+$',
                                    'images': True, 'box': False},
                },
                'question_types': ['noul', 'choice', 'score', 'box'],
                'provider_question_names': {'noul': 'noul', 'choice': 'choice', 'score': 'score', 'box': 'box'},
                'noul_criteria': True,
                'boolean_choice_values': False,
                'refusal_answers': False,
                'state_shapes': ['string', 'object', 'array'],
                'images': {'provider_documents': True, 'client_implements': True,
                           'requires': 'experimental_images opt-in; TypeSafe-Danger-Zone-Images header'},
                'box': {'provider_documents': True, 'client_implements': True,
                        'requires': 'experimental_images opt-in and pinned jev-1.14.0; pair with a presence noul'},
                'limits': {'questions': [1, 400], 'choices': [2, 255], 'levels': [2, 10],
                           'body_bytes': 33_554_432, 'nesting': 64},
                'retry_statuses': [429, 503, 529],
                'origin': dict(_DECISION_ORIGIN),
                'score_scale': 'expected_level_index_0_to_n_minus_1',
            },
        },
    },
    'openrouter': {
        'credential_env': 'OPENROUTER_API_KEY',
        'default_route': 'decisions',
        'routes': {
            'decisions': {
                'route': 'openrouter.decisions',
                'endpoint': 'https://openrouter.ai/api/alpha/decisions',
                'default_model': '~typesafe/jev-latest',
                'models': {
                    '~typesafe/jev-latest': {'match': 'alias', 'alias_pattern': r'^typesafe/jev-\d+\.\d+(?:\.\d+)?(?:-[0-9]{8})?$',
                                             'upstream_provider': 'TypeSafe', 'images': False, 'box': False},
                    'typesafe/jev-1.14': {'match': 'snapshot', 'upstream_provider': 'TypeSafe',
                                          'images': False, 'box': False},
                    'typesafe/jev-1.13': {'match': 'snapshot', 'upstream_provider': 'TypeSafe',
                                          'images': False, 'box': False},
                },
                'question_types': ['noul', 'choice', 'score'],
                'provider_question_names': {'noul': 'noul', 'choice': 'choice', 'score': 'score'},
                'noul_criteria': True,
                'boolean_choice_values': False,
                'refusal_answers': False,
                'state_shapes': ['string', 'object', 'array'],
                'images': {'provider_documents': True, 'client_implements': False},
                'box': {'provider_documents': True, 'client_implements': False},
                'limits': {'questions': [1, 400], 'choices': [2, 255], 'levels': [2, 10]},
                'retry_statuses': [429, 503, 529],
                'origin': {
                    'values': 'provider_decision_model_via_openrouter',
                    'confidence': 'provider_reported_optional',
                    'calibration': 'upstream_claim_not_verified_by_client',
                },
                'score_scale': 'expected_level_index_0_to_n_minus_1',
            },
            'structured': {
                'route': 'openrouter.structured',
                'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
                'default_model': None,
                'models': {},
                'question_types': ['noul', 'choice', 'score'],
                'provider_question_names': {},
                'noul_criteria': True,
                'boolean_choice_values': False,
                'refusal_answers': True,
                'state_shapes': ['string', 'object', 'array'],
                'images': {'provider_documents': True, 'client_implements': False},
                'box': {'provider_documents': False, 'client_implements': False},
                'limits': {'questions': [1, 100], 'choices': [2, 100], 'levels': [2, 10]},
                'retry_statuses': [429, 503, 529],
                'origin': {
                    'values': 'llm_generated_json_uncalibrated',
                    'confidence': 'not_provided',
                    'calibration': 'none',
                    'score': 'client_derived_from_generated_level_probabilities',
                },
                'score_scale': 'expected_level_index_0_to_n_minus_1',
                'model_required': True,
            },
        },
    },
}

# Dated snapshot (-YYYYMMDD or -YYYY-MM-DD) and, for dotted versions, an extra patch number.
_SNAPSHOT_SUFFIX = r'(?:\.\d+)?(?:-(?:\d{8}|\d{4}-\d{2}-\d{2}))?'

_UNLISTED = {'match': 'snapshot', 'images': False, 'box': False, 'unlisted': True}


def provider_names():
    return tuple(PROVIDERS)


def _provider(name):
    if not isinstance(name, str) or name not in PROVIDERS:
        raise UsageError(f'provider must be one of: {", ".join(PROVIDERS)}')
    return PROVIDERS[name]


def route_key(provider, openrouter_mode=None):
    spec = _provider(provider)
    if provider == 'openrouter':
        mode = openrouter_mode or spec['default_route']
        if not isinstance(mode, str) or mode not in OPENROUTER_MODES:
            raise UsageError('openrouter mode must be decisions or structured')
        return mode
    if openrouter_mode is not None and openrouter_mode != spec['default_route']:
        raise UsageError('--openrouter-mode applies only to --provider openrouter')
    return spec['default_route']


def route_spec(provider, openrouter_mode=None):
    return _provider(provider)['routes'][route_key(provider, openrouter_mode)]


def credential_env(provider):
    return _provider(provider)['credential_env']


def default_model(provider, openrouter_mode=None):
    return route_spec(provider, openrouter_mode)['default_model']


def resolve_model(provider, model=None, openrouter_mode=None, allow_unlisted=False):
    """Return (model_id, model_caps). Never substitutes another model silently."""
    spec = route_spec(provider, openrouter_mode)
    if model is None:
        model = spec['default_model']
        if model is None:
            raise UsageError(f'{spec["route"]} requires an explicit --model; no default is chosen for you')
    if not isinstance(model, str) or not model or len(model) > 200 or any(ord(c) <= 32 for c in model):
        raise UsageError('model must be a non-empty identifier without whitespace')
    if model in spec['models']:
        return model, dict(spec['models'][model])
    if spec.get('model_required') or allow_unlisted:
        return model, dict(_UNLISTED)
    raise CapabilityError(f'model {model!r} is not in the {spec["route"]} capability table; '
                          'pass --allow-unlisted-model to use it with base capabilities')


def reported_model_ok(requested, reported, caps):
    if not isinstance(reported, str) or not reported:
        return False
    match = caps.get('match')
    if match == 'exact':
        return reported == requested
    if match == 'alias':
        return re.fullmatch(caps['alias_pattern'], reported) is not None
    return re.fullmatch(re.escape(requested) + _SNAPSHOT_SUFFIX, reported) is not None


def matrix():
    """A JSON-safe deep copy for listing; contains env variable names, never values."""
    providers = {}
    for name, spec in PROVIDERS.items():
        entry = copy.deepcopy(spec)
        for route in entry['routes'].values():
            for caps in route['models'].values():
                caps.pop('alias_pattern', None)
        providers[name] = entry
    return {
        'schema_version': 'jev.capabilities.v1',
        'checked_on': CHECKED_ON,
        'default_provider': DEFAULT_PROVIDER,
        'providers': providers,
        'notes': [
            'Live calls require an explicit --live (CLI) or operator-enabled MCP live mode.',
            'Each provider reads only its own credential environment variable at call time.',
            'Score values are expected 0-based level indices; values from different providers or models '
            'are not interchangeable and need separate thresholds.',
            'openrouter.structured values are generated by a general model and are not calibrated.',
        ],
    }
