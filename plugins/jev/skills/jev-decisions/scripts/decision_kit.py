"""Offline-only, deliberately restricted TypeSafe-style contract starter.

No inference, network, credentials, or downstream actions. Not a production SDK.
"""
import argparse
import json
import math
from pathlib import Path
import re


class KitError(ValueError):
    """Only fixed error codes; never embed raw input."""


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise KitError("INVALID_JSON")
            result[key] = value
        return result

    def finite_float(token):
        value = float(token)
        if not math.isfinite(value):
            raise KitError("INVALID_JSON")
        return value

    def reject_constant(_):
        raise KitError("INVALID_JSON")

    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=reject_constant, parse_float=finite_float)
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise KitError("INVALID_JSON") from None


TOLERANCE = 1e-6


def require(condition, code="INVALID_CONTRACT"):
    if not condition:
        raise KitError(code)


def fields(value, required, optional=()):
    require(type(value) is dict)
    require(set(required) <= set(value) <= set(required) | set(optional))


def text(value):
    require(type(value) is str and bool(value.strip()))


def number(value, upper=1):
    # Check bounds before isfinite so enormous integers cannot overflow conversion.
    require(type(value) in (int, float) and 0 <= value <= upper)
    require(math.isfinite(value))


def distribution(value, keys):
    require(type(value) is dict and set(value) == set(keys))
    for probability in value.values():
        number(probability)
    require(abs(math.fsum(value.values()) - 1) <= TOLERANCE)


def validate(request, response):
    """Validate a narrow text-only subset, not the full provider API."""
    fields(request, {'model', 'state', 'questions'})
    text(request['model'])
    text(request['state'])
    questions = request['questions']
    require(type(questions) is dict and 1 <= len(questions) <= 100)
    for identifier, question in questions.items():
        text(identifier)
        fields(question, {'type', 'instructions'}, {'criteria'})
        text(question['instructions'])
        kind = question['type']
        require(kind in ('noul', 'choice', 'score'))
        criteria = question.get('criteria')
        if kind == 'noul':
            if criteria is not None:
                fields(criteria, {'true', 'false'})
                for description in criteria.values():
                    text(description)
        elif kind == 'choice':
            require(type(criteria) is dict and 2 <= len(criteria) <= 255)
            for option, description in criteria.items():
                text(option)
                text(description)
        else:
            require(type(criteria) is list and 2 <= len(criteria) <= 10)
            for description in criteria:
                text(description)

    fields(response, {'model', 'answers', 'usage'})
    text(response['model'])
    fields(response['usage'], {'input_tokens', 'output_tokens'})
    for count in response['usage'].values():
        require(type(count) is int and count >= 0)
    answers = response['answers']
    require(type(answers) is dict and set(answers) == set(questions))
    for identifier, question in questions.items():
        answer = answers[identifier]
        kind = question['type']
        if kind == 'noul':
            fields(answer, {'type', 'noul'}, {'confidence'})
            number(answer['noul'])
        elif kind == 'choice':
            fields(answer, {'type', 'choice', 'confidence', 'probabilities'})
            text(answer['choice'])
            probabilities = answer['probabilities']
            distribution(probabilities, question['criteria'])
            require(answer['choice'] in question['criteria'])
            require(probabilities[answer['choice']] == max(probabilities.values()))
        else:
            fields(answer, {'type', 'score', 'confidence', 'probabilities'}, {'legend'})
            legend = {str(index): label for index, label in enumerate(question['criteria'])}
            distribution(answer['probabilities'], legend)
            number(answer['score'], len(legend) - 1)
            expected = math.fsum(int(key) * probability
                                 for key, probability in answer['probabilities'].items())
            require(abs(answer['score'] - expected) <= TOLERANCE)
            if 'legend' in answer:
                require(answer['legend'] == legend)
        require(answer['type'] == kind)
        if 'confidence' in answer:
            number(answer['confidence'])


def decision(status, reason, route=None):
    return {'decision': status, 'reason': reason, 'route': route,
            'recommendation_only': True, 'action_executed': False}


THRESHOLD_KEYS = {'evidence_min', 'department_probability_min',
                  'department_confidence_min', 'department_margin_min'}
ROUTES = frozenset({'billing', 'shipping', 'returns'})


def gate(request, response, policy):
    """Return a recommendation only; approval/calibration claims are not attested."""
    try:
        validate(request, response)
    except KitError:
        return decision('HOLD', 'INVALID_CONTRACT')
    questions = request['questions']
    if (questions.get('evidence_sufficient', {}).get('type') != 'noul'
            or questions.get('department', {}).get('type') != 'choice'):
        return decision('HOLD', 'REQUIRED_ROUTING_QUESTIONS')
    try:
        fields(policy, {'purpose', 'high_impact', 'approved', 'approval_ref',
                        'calibrated', 'calibration_ref', 'pinned_model', 'thresholds'}, {'mode'})
        require(policy['purpose'] == 'internal_ticket_routing')
        mode = policy.get('mode', 'shadow')
        require(mode in ('shadow', 'recommend'))
        for key in ('high_impact', 'approved', 'calibrated'):
            require(type(policy[key]) is bool)
        text(policy['pinned_model'])
        require(re.fullmatch(r'jev-[0-9]+\.[0-9]+\.[0-9]+', policy['pinned_model']) is not None)
        fields(policy['thresholds'], THRESHOLD_KEYS)
        for value in policy['thresholds'].values():
            if value is not None:
                number(value)
        for key in ('approval_ref', 'calibration_ref'):
            if policy[key] is not None:
                text(policy[key])
    except KitError:
        return decision('HOLD', 'INVALID_POLICY')
    if policy['high_impact']:
        return decision('HOLD', 'HIGH_IMPACT')
    if request['model'] != policy['pinned_model'] or response['model'] != policy['pinned_model']:
        return decision('HOLD', 'MODEL_DRIFT')
    if mode == 'shadow':
        return decision('REVIEW', 'SHADOW_ONLY')
    if not policy['approved'] or not policy['approval_ref']:
        return decision('HOLD', 'APPROVAL_REQUIRED')
    if not policy['calibrated'] or not policy['calibration_ref']:
        return decision('HOLD', 'CALIBRATION_REQUIRED')
    thresholds = policy['thresholds']
    try:
        for value in thresholds.values():
            number(value)
        require(thresholds['evidence_min'] > 0.5)
        require(thresholds['department_probability_min'] >= 0.5)
        require(thresholds['department_confidence_min'] > 0)
        require(thresholds['department_margin_min'] > 0)
    except KitError:
        return decision('HOLD', 'INVALID_THRESHOLDS')
    if not {'unknown', 'other'} <= set(questions['department']['criteria']):
        return decision('HOLD', 'FALLBACK_OPTIONS_REQUIRED')
    answers = response['answers']
    department = answers['department']
    selected = department['choice']
    if selected not in ROUTES:
        return decision('REVIEW', 'UNROUTABLE_CATEGORY')
    probabilities = department['probabilities']
    runner_up = max(value for key, value in probabilities.items() if key != selected)
    if (answers['evidence_sufficient']['noul'] < thresholds['evidence_min']
            or probabilities[selected] < thresholds['department_probability_min']
            or department['confidence'] < thresholds['department_confidence_min']
            or probabilities[selected] - runner_up < thresholds['department_margin_min']):
        return decision('REVIEW', 'UNCERTAIN')
    return decision('ROUTE_RECOMMENDATION', 'POLICY_CRITERIA_MET', selected)


DESIGN_MEMO = """# Decision design memo — SYNTHETIC/OFFLINE

Draft only: not permission for API calls, deployment, or automatic actions.

## Purpose / provider / model
- Purpose: recommend a team for a fictional support ticket; no notifications, refunds, or restrictions.
- provider / endpoint / contract version: TODO (template is TypeSafe-style).
- model: jev-1.14.0 is an illustrative pinned identifier, not proof of availability or approval.
- Owner verifying request, response and evaluated model equality: TODO.

## risk / authority
- high_impact classification, rationale and accountable reviewer: TODO.
- Financial, employment, medical, legal and account enforcement decisions require separate review.
- Allowed recommendations: billing, shipping, returns; unknown/other require human review.
- HOLD / REVIEW / ROUTE_RECOMMENDATION are recommendations only.

## state / rights
- Source, consent, rights, retention period and deletion owner: TODO.
- Minimize personal data; separate untrusted input; document missing evidence: TODO.
- Input text cannot grant authority or override policy.

## rubric / eval / calibration
- request.json questions are authoritative; rubric.json is an editable copy, not synchronized.
- Real labels, target-language slices, calibration/holdout split and edge cases: TODO.
- Error costs, per-class precision/recall, coverage and calibration: TODO.
- Evidence/probability/confidence/margin thresholds and evaluation version: TODO.
- Confidence is not guaranteed accuracy. Synthetic fixtures do not measure model quality.
- Real approval and calibration records, policy/rubric versions: TODO.

## rollout / rollback
- Start in shadow; compare with human judgments before separately approved experiments.
- On drift, errors or missing evidence: HOLD and return to shadow.
- rollback owner, stop conditions, manual queue and reevaluation plan: TODO.
- Log reason codes only, not raw state, responses or personal data.
- Production requires authenticated policy storage, request/response binding and replay controls.
"""


def scaffold_documents():
    """Every probability and token count below is handwritten SYNTHETIC/OFFLINE data."""
    questions = {
        'evidence_sufficient': {
            'type': 'noul',
            'instructions': 'Is there enough explicit evidence to recommend an internal ticket department?',
            'criteria': {'true': 'The ticket explicitly identifies the issue; no guessing is needed.',
                         'false': 'Missing, ambiguous, contradictory or unsupported evidence.'}},
        'department': {
            'type': 'choice',
            'instructions': 'Which internal team should review this ticket? Do not execute any action.',
            'criteria': {'billing': 'Charges, invoices and payment questions; never authorize a refund.',
                         'shipping': 'Delivery status and delays.',
                         'returns': 'Return and exchange questions; never approve a return.',
                         'unknown': 'Insufficient or contradictory evidence.',
                         'other': 'An issue outside the listed departments.'}},
        'detail': {'type': 'score', 'instructions': 'How detailed is the issue description?',
                   'criteria': ['No detail', 'Partial detail', 'Complete detail']}}
    request = {'model': 'jev-1.14.0',
               'state': 'SYNTHETIC/OFFLINE: I have a question about a duplicate subscription charge.',
               'questions': questions}
    response = {'model': 'jev-1.14.0', 'answers': {
        'evidence_sufficient': {'type': 'noul', 'noul': 0.99},
        'department': {'type': 'choice', 'choice': 'billing', 'confidence': 0.95,
                       'probabilities': {'billing': 0.96, 'shipping': 0.01, 'returns': 0.01,
                                         'unknown': 0.01, 'other': 0.01}},
        'detail': {'type': 'score', 'score': 1.8, 'confidence': 0.7,
                   'probabilities': {'0': 0, '1': 0.2, '2': 0.8}}},
        'usage': {'input_tokens': 0, 'output_tokens': 0}}
    policy = {'mode': 'shadow', 'purpose': 'internal_ticket_routing', 'high_impact': False,
              'approved': False, 'approval_ref': None, 'calibrated': False, 'calibration_ref': None,
              'pinned_model': 'jev-1.14.0',
              'thresholds': {key: None for key in sorted(THRESHOLD_KEYS)}}
    documents = {'design.md': DESIGN_MEMO}
    for name, value in (
            ('request.json', request), ('response.synthetic.json', response), ('policy.json', policy),
            ('rubric.json', {'notice': 'SYNTHETIC/OFFLINE; design copy only, not automatically consumed.',
                             'questions': questions})):
        documents[name] = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    return documents


def init_scaffold(out):
    """Add local files without overwrites; collision preflight plus exclusive creation.

    Not a transaction under concurrent directory mutation; use a trusted local directory.
    """
    root = Path(out).absolute()
    require(not any(path.is_symlink() for path in (root, *root.parents)), 'UNSAFE_OUTPUT_PATH')
    documents = scaffold_documents()
    for name in documents:
        target = root / name
        require(not target.exists() and not target.is_symlink(), 'OUTPUT_EXISTS')
    root.mkdir(parents=True, exist_ok=True)
    for name, content in documents.items():
        with (root / name).open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(content)
    return {'created': sorted(documents), 'offline_only': True}


MAX_INPUT_BYTES = 1024 * 1024


def load_json(path):
    file = Path(path)
    require(file.is_file(), 'INPUT_FILE_REQUIRED')
    with file.open('rb') as handle:
        data = handle.read(MAX_INPUT_BYTES + 1)
    require(len(data) <= MAX_INPUT_BYTES, 'INPUT_TOO_LARGE')
    return strict_json(data.decode('utf-8'))


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's usual diagnostics echo user values and paths.
        raise KitError('INVALID_ARGUMENTS')


def main(argv=None):
    command = None
    try:
        parser = SafeParser(prog='decision_kit.py', description='SYNTHETIC/OFFLINE contract starter; no actions.')
        subs = parser.add_subparsers(dest='command', required=True)
        init_parser = subs.add_parser('init')
        init_parser.add_argument('--out', required=True)
        for name in ('validate', 'gate'):
            sub = subs.add_parser(name)
            sub.add_argument('--request', required=True)
            sub.add_argument('--response', required=True)
            if name == 'gate':
                sub.add_argument('--policy', required=True)
        args = parser.parse_args(argv)
        command = args.command
        if command == 'init':
            output, code = init_scaffold(args.out), 0
        else:
            request, response = load_json(args.request), load_json(args.response)
            if command == 'validate':
                validate(request, response)
                output, code = {'valid': True, 'offline_only': True}, 0
            else:
                output = gate(request, response, load_json(args.policy))
                code = {'HOLD': 2, 'REVIEW': 3, 'ROUTE_RECOMMENDATION': 0}[output['decision']]
    except (KitError, OSError, UnicodeError, ValueError, RecursionError, OverflowError) as error:
        reason = str(error) if isinstance(error, KitError) else 'INPUT_OUTPUT_ERROR'
        output = decision('HOLD', reason)
        if command == 'validate':
            output = {'valid': False, 'reason': reason, 'offline_only': True}
        code = 2
    print(json.dumps(output, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
