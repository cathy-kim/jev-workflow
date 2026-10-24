"""Common request contract, provider payloads and response parsing. Offline only."""
import base64
import json
import math
import unittest

from client_fixtures import (FAKE_KEYS, OPENAI_RESPONSE, OPENROUTER_DECISIONS_RESPONSE, PNG_1X1,
                             REQUEST, TYPESAFE_RESPONSE, fresh, structured_response)
from jev_workflow import capabilities
from jev_workflow.client import DecisionClient
from jev_workflow.errors import CapabilityError, ResponseError, UsageError
from jev_workflow.model import parse_request


def client(provider, **kwargs):
    return DecisionClient(provider, environ={}, **kwargs)


class RequestValidationTests(unittest.TestCase):
    def test_valid_request_is_immutable(self):
        request = parse_request(fresh(REQUEST))
        self.assertEqual([q.id for q in request.questions], ['billing', 'team', 'urgency'])
        with self.assertRaises(Exception):
            request.questions = ()
        state = request.state
        state_copy = request.state
        self.assertEqual(state, state_copy)
        self.assertIsInstance(request.questions, tuple)

    def test_object_state_is_copied_not_shared(self):
        raw = fresh(REQUEST)
        raw['state'] = {'ticket': 'Synthetic duplicate charge'}
        request = parse_request(raw)
        raw['state']['ticket'] = 'mutated'
        view = request.state
        view['ticket'] = 'mutated again'
        self.assertEqual(request.state, {'ticket': 'Synthetic duplicate charge'})

    def test_predicate_alias_normalizes_to_noul(self):
        raw = fresh(REQUEST)
        raw['questions'][0]['type'] = 'predicate'
        self.assertEqual(parse_request(raw).questions[0].type, 'noul')

    def invalid(self, mutate, fragment):
        raw = fresh(REQUEST)
        mutate(raw)
        with self.assertRaises(UsageError) as caught:
            parse_request(raw)
        self.assertIn(fragment, str(caught.exception))

    def test_rejects_structural_errors(self):
        cases = [
            (lambda r: r.pop('questions'), 'questions'),
            (lambda r: r.update(questions=[]), 'questions'),
            (lambda r: r.update(extra=1), 'unknown'),
            (lambda r: r.update(schema_version='jev.request.v0'), 'schema_version'),
            (lambda r: r['questions'][1].update(id='billing'), 'duplicate'),
            (lambda r: r['questions'][0].update(id='1bad id'), 'id'),
            (lambda r: r['questions'][0].update(type='rank'), 'type'),
            (lambda r: r['questions'][0].update(instructions=''), 'instructions'),
            (lambda r: r['questions'][0].update(options=[]), 'unknown'),
            (lambda r: r['questions'][1].update(options=[{'value': 'only'}]), '2'),
            (lambda r: r['questions'][1]['options'].append({'value': 'billing'}), 'distinct'),
            (lambda r: r['questions'][1]['options'].append({'value': 3}), 'string or boolean'),
            (lambda r: r['questions'][1]['options'].append({'value': ''}), 'empty'),
            (lambda r: r['questions'][2].update(levels=[{'label': 'one'}]), '2'),
            (lambda r: r['questions'][2].update(levels=[{'label': str(i)} for i in range(11)]), '10'),
            (lambda r: r['questions'][0].update(criteria={'true': 'yes'}), 'criteria'),
            (lambda r: r.update(state=float('nan')), 'state'),
            (lambda r: r.update(state={'n': float('inf')}), 'finite'),
            (lambda r: r.update(state=None), 'state'),
        ]
        for mutate, fragment in cases:
            with self.subTest(fragment=fragment):
                self.invalid(mutate, fragment)

    def test_too_many_questions(self):
        raw = fresh(REQUEST)
        raw['questions'] = [{'id': f'q{i}', 'type': 'noul', 'instructions': 'x?'} for i in range(401)]
        with self.assertRaises(UsageError):
            parse_request(raw)

    def test_typed_choices_distinguish_string_and_boolean(self):
        raw = fresh(REQUEST)
        raw['questions'][1]['options'] = [{'value': True}, {'value': 'true'}, {'value': False}]
        request = parse_request(raw)
        self.assertEqual([o.value for o in request.questions[1].options], [True, 'true', False])
        raw['questions'][1]['options'].append({'value': True})
        with self.assertRaises(UsageError):
            parse_request(raw)

    def test_deep_state_rejected(self):
        raw = fresh(REQUEST)
        node = {}
        raw['state'] = node
        for _ in range(70):
            node['n'] = {}
            node = node['n']
        with self.assertRaises(UsageError):
            parse_request(raw)


class CapabilityTests(unittest.TestCase):
    def test_provider_defaults_are_pinned_separately(self):
        self.assertEqual(capabilities.DEFAULT_PROVIDER, 'openrouter')
        self.assertEqual(capabilities.default_model('openai'), 'gpt-6-luna')
        self.assertEqual(capabilities.default_model('typesafe'), 'jev-1.14.0')
        self.assertEqual(capabilities.default_model('openrouter', 'decisions'), '~typesafe/jev-latest')
        self.assertIsNone(capabilities.default_model('openrouter', 'structured'))

    def test_matrix_lists_three_providers_with_env_names_only(self):
        matrix = capabilities.matrix()
        self.assertEqual(set(matrix['providers']), {'openai', 'typesafe', 'openrouter'})
        self.assertEqual(matrix['providers']['openai']['credential_env'], 'OPENAI_API_KEY')
        self.assertEqual(matrix['providers']['typesafe']['credential_env'], 'TYPESAFE_API_KEY')
        self.assertEqual(matrix['providers']['openrouter']['credential_env'], 'OPENROUTER_API_KEY')
        text = json.dumps(matrix)
        for key in FAKE_KEYS.values():
            self.assertNotIn(key, text)
        structured = matrix['providers']['openrouter']['routes']['structured']
        self.assertEqual(structured['origin']['values'], 'llm_generated_json_uncalibrated')

    def test_unlisted_model_requires_explicit_opt_in(self):
        with self.assertRaises(CapabilityError):
            client('openai', model='gpt-unknown')
        self.assertEqual(client('openai', model='gpt-unknown', allow_unlisted_model=True).model, 'gpt-unknown')

    def test_structured_route_requires_explicit_model(self):
        with self.assertRaises(UsageError):
            client('openrouter', openrouter_mode='structured')

    def test_unknown_provider(self):
        with self.assertRaises(UsageError):
            client('anthropic')


class OpenAIPayloadTests(unittest.TestCase):
    def test_payload_matches_official_shape(self):
        prepared = client('openai').prepare(parse_request(fresh(REQUEST)))
        self.assertEqual(prepared.endpoint, 'https://api.openai.com/v1/decisions')
        body = prepared.body
        self.assertEqual(body['model'], 'gpt-6-luna')
        self.assertEqual(body['input'], REQUEST['state'])
        self.assertEqual(body['questions'][0], {'type': 'predicate', 'name': 'billing',
                                                'instructions': 'Is this message about billing?'})
        self.assertEqual(body['questions'][1]['choices'][2], {'value': 'other'})
        self.assertEqual(body['questions'][2]['levels'][2],
                         {'label': 'Today', 'description': 'Blocking work right now.'})
        self.assertNotIn('Authorization', prepared.headers)

    def test_object_state_uses_input_json(self):
        raw = fresh(REQUEST)
        raw['state'] = {'ticket': 'Synthetic'}
        body = client('openai').prepare(parse_request(raw)).body
        self.assertEqual(body['input'], [{'role': 'user', 'content': [
            {'type': 'input_json', 'data': {'ticket': 'Synthetic'}}]}])

    def test_boolean_choice_values_are_supported(self):
        raw = fresh(REQUEST)
        raw['questions'][1]['options'] = [{'value': True}, {'value': False}]
        body = client('openai').prepare(parse_request(raw)).body
        self.assertEqual(body['questions'][1]['choices'], [{'value': True}, {'value': False}])

    def test_unsupported_features_fail_before_transport(self):
        for mutate in (lambda r: r['questions'][0].update(criteria={'true': 'y', 'false': 'n'}),
                       lambda r: r['questions'].append({'id': 'where', 'type': 'box', 'instructions': 'x'}),
                       lambda r: r.update(state=['a', 'b'])):
            raw = fresh(REQUEST)
            mutate(raw)
            with self.subTest(raw=raw), self.assertRaises(CapabilityError):
                client('openai').prepare(parse_request(raw))


class OpenAIParseTests(unittest.TestCase):
    def setUp(self):
        self.request = parse_request(fresh(REQUEST))
        self.client = client('openai')

    def parse(self, response):
        return self.client.parse(self.request, response).to_dict()

    def test_parse_success(self):
        result = self.parse(fresh(OPENAI_RESPONSE))
        self.assertEqual(result['schema_version'], 'jev.result.v1')
        self.assertEqual(result['provider'], 'openai')
        self.assertEqual(result['model'], {'requested': 'gpt-6-luna', 'reported': 'gpt-6-luna'})
        answers = {a['id']: a for a in result['answers']}
        self.assertEqual(answers['billing']['value'], 0.91)
        self.assertEqual(answers['team']['value'], 'billing')
        self.assertAlmostEqual(answers['urgency']['value'], 1.1)
        self.assertAlmostEqual(answers['urgency']['derived']['normalized_0_1'], 0.55)
        self.assertEqual(answers['urgency']['derived']['scale'], 'expected_level_index')
        self.assertEqual(result['origin']['values'], 'provider_decision_model')
        self.assertTrue(result['recommendation_only'])
        self.assertEqual(result['usage']['input_tokens'], 120)

    def test_refusal_is_distinct_from_false(self):
        response = fresh(OPENAI_RESPONSE)
        response['answers'][0] = {'type': 'refusal', 'name': 'billing'}
        result = self.parse(response)
        first = result['answers'][0]
        self.assertEqual(first['status'], 'refused')
        self.assertIsNone(first['value'])
        self.assertEqual(result['summary'], {'answered': 2, 'refused': 1, 'not_applicable': 0})

    def test_boolean_choice_answer(self):
        raw = fresh(REQUEST)
        raw['questions'][1]['options'] = [{'value': True}, {'value': 'true'}]
        request = parse_request(raw)
        response = fresh(OPENAI_RESPONSE)
        response['answers'][1].update(choice=True, probabilities=[
            {'value': True, 'probability': 0.6}, {'value': 'true', 'probability': 0.4}])
        answer = self.client.parse(request, response).to_dict()['answers'][1]
        self.assertIs(answer['value'], True)
        response['answers'][1]['choice'] = 1
        with self.assertRaises(ResponseError):
            self.client.parse(request, response)

    def test_malformed_responses_fail_closed(self):
        def mutate(fn):
            response = fresh(OPENAI_RESPONSE)
            fn(response)
            return response
        cases = {
            'missing answer': lambda r: r['answers'].pop(),
            'extra answer': lambda r: r['answers'].append({'type': 'refusal', 'name': 'x'}),
            'reordered': lambda r: r['answers'].reverse(),
            'duplicate': lambda r: r['answers'].__setitem__(1, r['answers'][0]),
            'wrong type': lambda r: r['answers'][0].update(type='choice'),
            'nan': lambda r: r['answers'][0].update(probability=float('nan')),
            'bool number': lambda r: r['answers'][0].update(probability=True),
            'out of range': lambda r: r['answers'][0].update(probability=1.2),
            'unknown field': lambda r: r['answers'][0].update(rationale='x'),
            'unknown option': lambda r: r['answers'][1].update(choice='sales'),
            'bad sum': lambda r: r['answers'][1]['probabilities'][0].update(probability=0.5),
            'missing option prob': lambda r: r['answers'][1]['probabilities'].pop(),
            'score out of scale': lambda r: r['answers'][2].update(score=2.5),
            'score label drift': lambda r: r['answers'][2]['probabilities'][0].update(label='Other'),
            'negative usage': lambda r: r['usage'].update(input_tokens=-2147483648),
            'model drift': lambda r: r.update(model='gpt-other'),
            'no answers': lambda r: r.pop('answers'),
            'confidence nan': lambda r: r['answers'][1].update(confidence=float('inf')),
        }
        for name, fn in cases.items():
            with self.subTest(case=name), self.assertRaises(ResponseError):
                self.parse(mutate(fn))
        with self.assertRaises(ResponseError):
            self.parse(['not', 'an', 'object'])

    def test_dated_snapshot_model_is_recorded(self):
        response = fresh(OPENAI_RESPONSE)
        response['model'] = 'gpt-6-luna-2026-10-01'
        result = self.parse(response)
        self.assertEqual(result['model']['reported'], 'gpt-6-luna-2026-10-01')


class TypeSafePayloadTests(unittest.TestCase):
    def test_payload_matches_system_one_shape(self):
        prepared = client('typesafe').prepare(parse_request(fresh(REQUEST)))
        self.assertEqual(prepared.endpoint, 'https://api.typesafe.ai/v1/systemone')
        body = prepared.body
        self.assertEqual(body['model'], 'jev-1.14.0')
        self.assertEqual(list(body['questions']), ['billing', 'team', 'urgency'])
        self.assertEqual(body['questions']['team']['criteria'],
                         {'billing': 'Payments and refunds.', 'technical': 'Problems using the product.',
                          'other': None})
        self.assertEqual(body['questions']['urgency']['criteria'],
                         ['Can wait', 'This week', {'label': 'Today', 'description': 'Blocking work right now.'}])
        self.assertNotIn('TypeSafe-Danger-Zone-Images', prepared.headers)

    def test_noul_criteria(self):
        raw = fresh(REQUEST)
        raw['questions'][0]['criteria'] = {'true': 'About payments', 'false': 'Anything else'}
        body = client('typesafe').prepare(parse_request(raw)).body
        self.assertEqual(body['questions']['billing']['criteria'], {'true': 'About payments', 'false': 'Anything else'})

    def test_boolean_choice_unsupported(self):
        raw = fresh(REQUEST)
        raw['questions'][1]['options'] = [{'value': True}, {'value': False}]
        with self.assertRaises(CapabilityError):
            client('typesafe').prepare(parse_request(raw))

    def image_request(self, *, box=True):
        raw = fresh(REQUEST)
        raw['state'] = {'photo': 'img-synthetic-1'}
        raw['images'] = [{'ref': 'img-synthetic-1', 'format': 'png',
                          'data_base64': base64.b64encode(PNG_1X1).decode('ascii')}]
        raw['questions'] = [{'id': 'present', 'type': 'noul', 'instructions': 'Is a square visible in `photo`?'}]
        if box:
            raw['questions'].append({'id': 'where', 'type': 'box', 'instructions': 'the square in `photo`'})
        return parse_request(raw)

    def test_images_and_box_require_explicit_experimental_consent(self):
        with self.assertRaises(CapabilityError):
            client('typesafe').prepare(self.image_request())
        prepared = client('typesafe', experimental_images=True).prepare(self.image_request())
        self.assertEqual(prepared.headers['TypeSafe-Danger-Zone-Images'], 'true')
        self.assertEqual(prepared.body['assets']['img-synthetic-1']['format'], 'png')
        self.assertEqual(prepared.body['questions']['where'], {'type': 'box', 'instructions': 'the square in `photo`'})

    def test_box_requires_pinned_jev_1_14(self):
        for model in ('jev-1.13.0', 'jev-latest', 'jev-preview'):
            with self.subTest(model=model), self.assertRaises(CapabilityError):
                client('typesafe', model=model, experimental_images=True).prepare(self.image_request())
        prepared = client('typesafe', model='jev-1.13.0', experimental_images=True).prepare(
            self.image_request(box=False))
        self.assertIn('assets', prepared.body)

    def test_image_validation(self):
        raw = fresh(REQUEST)
        raw['images'] = [{'ref': 'missing-ref', 'format': 'png',
                          'data_base64': base64.b64encode(PNG_1X1).decode('ascii')}]
        with self.assertRaises(UsageError):
            parse_request(raw)
        raw['state'] = 'see missing-ref'
        raw['images'][0]['data_base64'] = base64.b64encode(b'GIF89a not png').decode('ascii')
        with self.assertRaises(UsageError):
            parse_request(raw)
        raw['images'][0].update(format='png', data_base64='###')
        with self.assertRaises(UsageError):
            parse_request(raw)
        raw['images'][0] = {'ref': 'missing-ref', 'url': 'https://example.com/x.png'}
        with self.assertRaises(UsageError):
            parse_request(raw)

    def test_images_unsupported_on_other_providers_before_transport(self):
        request = self.image_request(box=False)
        with self.assertRaises(CapabilityError):
            client('openai', experimental_images=True).prepare(request)
        with self.assertRaises(CapabilityError):
            client('openrouter', experimental_images=True).prepare(request)


class TypeSafeParseTests(unittest.TestCase):
    def setUp(self):
        self.request = parse_request(fresh(REQUEST))

    def test_parse_success(self):
        result = client('typesafe').parse(self.request, fresh(TYPESAFE_RESPONSE)).to_dict()
        answers = {a['id']: a for a in result['answers']}
        self.assertEqual(answers['billing']['value'], 0.93)
        self.assertEqual(answers['team']['probabilities'][0], {'value': 'billing', 'probability': 0.92})
        self.assertAlmostEqual(answers['urgency']['derived']['normalized_0_1'], 0.715)
        self.assertEqual(result['origin']['values'], 'provider_decision_model')
        self.assertEqual(result['usage'], {'input_tokens': 140, 'output_tokens': 12})

    def test_alias_resolution_recorded_but_pinned_model_exact(self):
        response = fresh(TYPESAFE_RESPONSE)
        result = client('typesafe', model='jev-latest').parse(self.request, response).to_dict()
        self.assertEqual(result['model'], {'requested': 'jev-latest', 'reported': 'jev-1.14.0'})
        response['model'] = 'jev-1.13.0'
        with self.assertRaises(ResponseError):
            client('typesafe').parse(self.request, response)
        response['model'] = 'other-model'
        with self.assertRaises(ResponseError):
            client('typesafe', model='jev-latest').parse(self.request, response)

    def test_malformed(self):
        cases = {
            'missing': lambda r: r['answers'].pop('team'),
            'unknown id': lambda r: r['answers'].update(extra={'type': 'noul', 'noul': 0.1}),
            'type': lambda r: r['answers']['billing'].update(type='choice'),
            'legend keys': lambda r: r['answers']['urgency']['legend'].pop('2'),
            'prob keys': lambda r: r['answers']['team']['probabilities'].pop('other'),
            'refusal unsupported': lambda r: r['answers'].update(billing={'type': 'refusal'}),
            'extra envelope': lambda r: r.update(debug=True),
            'usage': lambda r: r['usage'].update(output_tokens=1.5),
        }
        for name, fn in cases.items():
            response = fresh(TYPESAFE_RESPONSE)
            response['answers'] = fresh(response['answers'])
            fn(response)
            with self.subTest(case=name), self.assertRaises(ResponseError):
                client('typesafe').parse(self.request, response)

    def test_box_parse_and_nullable_confidence(self):
        raw = fresh(REQUEST)
        raw['state'] = {'photo': 'img-synthetic-1'}
        raw['images'] = [{'ref': 'img-synthetic-1', 'format': 'png',
                          'data_base64': base64.b64encode(PNG_1X1).decode('ascii')}]
        raw['questions'] = [{'id': 'where', 'type': 'box', 'instructions': 'the square in `photo`'}]
        request = parse_request(raw)
        typesafe = client('typesafe', experimental_images=True)
        response = {'model': 'jev-1.14.0', 'usage': {'input_tokens': 9, 'output_tokens': 4},
                    'answers': {'where': {'type': 'box', 'confidence': None,
                                          'box': {'top': 0.2, 'bottom': 0.6, 'left': 0.1, 'right': 0.5}}}}
        answer = typesafe.parse(request, response).to_dict()['answers'][0]
        self.assertEqual(answer['value'], {'top': 0.2, 'bottom': 0.6, 'left': 0.1, 'right': 0.5})
        self.assertIsNone(answer['confidence'])
        self.assertIn('presence', answer['derived']['note'])
        response['answers']['where']['box']['left'] = 0.9
        with self.assertRaises(ResponseError):
            typesafe.parse(request, response)


class OpenRouterTests(unittest.TestCase):
    def setUp(self):
        self.request = parse_request(fresh(REQUEST))

    def test_decisions_route_is_default_and_preserves_legacy_endpoint(self):
        prepared = client('openrouter').prepare(self.request)
        self.assertEqual(prepared.endpoint, 'https://openrouter.ai/api/alpha/decisions')
        self.assertEqual(prepared.body['model'], '~typesafe/jev-latest')
        self.assertEqual(prepared.body['provider'], {'allow_fallbacks': False})
        self.assertIn('state', prepared.body)

    def test_decisions_parse_records_gateway_origin(self):
        result = client('openrouter').parse(self.request, fresh(OPENROUTER_DECISIONS_RESPONSE)).to_dict()
        self.assertEqual(result['route'], 'openrouter.decisions')
        self.assertEqual(result['origin']['values'], 'provider_decision_model_via_openrouter')
        self.assertEqual(result['model']['reported'], 'typesafe/jev-1.14-20261014')
        self.assertEqual(result['provenance']['upstream_provider'], 'TypeSafe')
        self.assertEqual(result['usage']['cost'], 0.00002)

    def test_decisions_detects_upstream_fallback(self):
        response = fresh(OPENROUTER_DECISIONS_RESPONSE)
        response['provider'] = 'SomeoneElse'
        with self.assertRaises(ResponseError):
            client('openrouter').parse(self.request, response)
        response = fresh(OPENROUTER_DECISIONS_RESPONSE)
        response['model'] = 'other/model'
        with self.assertRaises(ResponseError):
            client('openrouter').parse(self.request, response)

    def test_decisions_optional_fields_absent_are_null_not_zero(self):
        response = fresh(OPENROUTER_DECISIONS_RESPONSE)
        response['answers'] = fresh(response['answers'])
        response['answers']['team'] = {'type': 'choice', 'choice': 'billing'}
        answer = client('openrouter').parse(self.request, response).to_dict()['answers'][1]
        self.assertIsNone(answer['confidence'])
        self.assertIsNone(answer['probabilities'])

    def test_structured_route_payload(self):
        prepared = client('openrouter', openrouter_mode='structured', model='example/judge-model').prepare(self.request)
        self.assertEqual(prepared.endpoint, 'https://openrouter.ai/api/v1/chat/completions')
        body = prepared.body
        self.assertEqual(body['provider'], {'require_parameters': True, 'allow_fallbacks': False})
        self.assertEqual(body['response_format']['type'], 'json_schema')
        self.assertTrue(body['response_format']['json_schema']['strict'])
        schema = body['response_format']['json_schema']['schema']
        self.assertEqual(schema['properties']['answers']['required'], ['billing', 'team', 'urgency'])
        self.assertNotIn('models', body)
        self.assertFalse(body.get('stream', False))

    def test_structured_parse_marks_uncalibrated_and_not_applicable(self):
        structured = client('openrouter', openrouter_mode='structured', model='example/judge-model')
        result = structured.parse(self.request, structured_response()).to_dict()
        self.assertEqual(result['origin']['values'], 'llm_generated_json_uncalibrated')
        answers = {a['id']: a for a in result['answers']}
        self.assertEqual(answers['urgency']['status'], 'not_applicable')
        self.assertIsNone(answers['urgency']['value'])
        self.assertIsNone(answers['team']['confidence'])
        self.assertEqual(result['summary'], {'answered': 2, 'refused': 0, 'not_applicable': 1})

    def test_structured_score_is_client_derived(self):
        content = fresh(json.loads(structured_response()['choices'][0]['message']['content']))
        content['answers']['urgency'] = {'status': 'answered',
                                         'level_probabilities': {'0': 0.2, '1': 0.3, '2': 0.5}}
        structured = client('openrouter', openrouter_mode='structured', model='example/judge-model')
        answer = structured.parse(self.request, structured_response(content)).to_dict()['answers'][2]
        self.assertAlmostEqual(answer['value'], 1.3)
        self.assertEqual(answer['derived']['value_origin'], 'client_derived_from_generated_level_probabilities')

    def test_structured_failures(self):
        structured = client('openrouter', openrouter_mode='structured', model='example/judge-model')
        bad = [structured_response('{not json'), structured_response(finish='length'),
               structured_response(model='other/model'),
               structured_response({'answers': {'billing': {'status': 'answered', 'probability': 0.5}}}),
               structured_response({'answers': {
                   'billing': {'status': 'answered', 'probability': None},
                   'team': {'status': 'refused', 'choice': None, 'probabilities': None},
                   'urgency': {'status': 'refused', 'level_probabilities': None}}})]
        for response in bad:
            with self.subTest(response=response), self.assertRaises(ResponseError):
                structured.parse(self.request, response)

    def test_structured_whole_refusal(self):
        structured = client('openrouter', openrouter_mode='structured', model='example/judge-model')
        result = structured.parse(self.request, structured_response('', refusal='declined')).to_dict()
        self.assertEqual({a['status'] for a in result['answers']}, {'refused'})

    def test_structured_rejects_boolean_choices_and_box(self):
        raw = fresh(REQUEST)
        raw['questions'][1]['options'] = [{'value': True}, {'value': False}]
        structured = client('openrouter', openrouter_mode='structured', model='example/judge-model')
        with self.assertRaises(CapabilityError):
            structured.prepare(parse_request(raw))


class DerivedValueTests(unittest.TestCase):
    def test_probability_tolerance_scales_with_option_count(self):
        raw = fresh(REQUEST)
        raw['questions'] = [{'id': 'c', 'type': 'choice', 'instructions': 'Pick',
                             'options': [{'value': f'o{i}'} for i in range(100)]}]
        request = parse_request(raw)
        probabilities = {f'o{i}': 0.01 for i in range(100)}
        probabilities['o0'] = 0.04  # rounded distribution summing to 1.03
        response = {'model': 'jev-1.14.0', 'usage': {'input_tokens': 1, 'output_tokens': 1},
                    'answers': {'c': {'type': 'choice', 'choice': 'o0', 'confidence': 0.1,
                                      'probabilities': probabilities}}}
        result = client('typesafe').parse(request, response).to_dict()
        self.assertTrue(math.isclose(sum(p['probability'] for p in result['answers'][0]['probabilities']), 1.03))


if __name__ == '__main__':
    unittest.main()
