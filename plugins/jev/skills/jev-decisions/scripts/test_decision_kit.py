"""SYNTHETIC/OFFLINE: tests never perform inference or downstream actions."""
import ast
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("decision_kit.py")
if MODULE.exists():
    import decision_kit as kit
else:
    kit = None


class StrictJSONTests(unittest.TestCase):
    def test_parser_exists_and_accepts_json(self):
        self.assertIsNotNone(kit, "offline implementation not created yet")
        self.assertEqual(kit.strict_json('{"a": 1}'), {"a": 1})

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(kit.KitError):
            kit.strict_json('{"a":1,"a":2}')

    def test_nested_duplicate_rejected(self):
        with self.assertRaises(kit.KitError):
            kit.strict_json('{"a":{"b":1,"b":2}}')

    def test_nonfinite_constants_rejected(self):
        for token in ('NaN', 'Infinity', '-Infinity', '1e400'):
            with self.subTest(token=token), self.assertRaises(kit.KitError):
                kit.strict_json('{"value":' + token + '}')

    def test_invalid_json_is_sanitized(self):
        with self.assertRaisesRegex(kit.KitError, '^INVALID_JSON$'):
            kit.strict_json('PRIVATE_RAW_DATA')


def fixtures():
    request = {
        "model": "jev-1.14.0",
        "state": "SYNTHETIC/OFFLINE: duplicate subscription charge question.",
        "questions": {
            "evidence_sufficient": {"type": "noul", "instructions": "Is routing evidence sufficient?"},
            "department": {"type": "choice", "instructions": "Which internal team should review?",
                           "criteria": {"billing": "Charges", "shipping": "Delivery", "returns": "Returns",
                                        "unknown": "Insufficient evidence", "other": "Outside these teams"}},
            "detail": {"type": "score", "instructions": "How detailed is this report?",
                       "criteria": ["No detail", "Partial detail", "Complete detail"]}
        }
    }
    response = {
        "model": "jev-1.14.0",
        "answers": {
            "evidence_sufficient": {"type": "noul", "noul": 0.99},
            "department": {"type": "choice", "choice": "billing", "confidence": 0.95,
                           "probabilities": {"billing": 0.96, "shipping": 0.01, "returns": 0.01,
                                             "unknown": 0.01, "other": 0.01}},
            "detail": {"type": "score", "score": 1.8, "confidence": 0.7,
                       "probabilities": {"0": 0.0, "1": 0.2, "2": 0.8}}
        },
        "usage": {"input_tokens": 0, "output_tokens": 0}
    }
    return request, response


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.request, self.response = fixtures()

    def test_valid_text_response_without_noul_confidence(self):
        self.assertTrue(hasattr(kit, 'validate'), 'validator is missing')
        self.assertIsNone(kit.validate(self.request, self.response))

    def invalid(self):
        with self.assertRaises(kit.KitError):
            kit.validate(self.request, self.response)

    def test_missing_answer(self):
        del self.response['answers']['detail']
        self.invalid()

    def test_extra_answer(self):
        self.response['answers']['extra'] = {'type': 'noul', 'noul': 1}
        self.invalid()

    def test_wrong_answer_type(self):
        self.response['answers']['detail']['type'] = 'choice'
        self.invalid()

    def test_unsupported_question_type(self):
        self.request['questions']['detail']['type'] = 'box'
        self.invalid()

    def test_structured_state_unsupported(self):
        self.request['state'] = {'text': 'not supported'}
        self.invalid()

    def test_assets_unsupported(self):
        self.request['assets'] = {}
        self.invalid()

    def test_non_text_criteria(self):
        self.request['questions']['department']['criteria']['billing'] = {'text': 'charges'}
        self.invalid()

    def test_empty_questions(self):
        self.request['questions'] = {}
        self.invalid()

    def test_missing_instructions(self):
        del self.request['questions']['detail']['instructions']
        self.invalid()

    def test_reported_model_required(self):
        for bad in (None, '', ' ', False):
            with self.subTest(bad=bad):
                self.response['model'] = bad
                self.invalid()

    def test_noul_nonboolean_bounded_finite(self):
        for bad in (True, False, -0.01, 1.01, float('nan'), float('inf'), '0.9', 10**400):
            with self.subTest(bad=str(bad)):
                self.response['answers']['evidence_sufficient']['noul'] = bad
                self.invalid()

    def test_noul_endpoints(self):
        for value in (0, 1):
            self.response['answers']['evidence_sufficient']['noul'] = value
            kit.validate(self.request, self.response)

    def test_optional_noul_confidence_checked_if_present(self):
        self.response['answers']['evidence_sufficient']['confidence'] = True
        self.invalid()

    def test_choice_probability_values(self):
        for bad in (True, -0.01, 1.01, float('nan'), float('inf'), '0.96'):
            with self.subTest(bad=bad):
                self.response['answers']['department']['probabilities']['billing'] = bad
                self.invalid()

    def test_probability_sum_outside_tolerance(self):
        self.response['answers']['department']['probabilities']['billing'] = 0.97
        self.invalid()

    def test_probability_sum_rounding_tolerance(self):
        self.response['answers']['department']['probabilities']['billing'] += 0.0000005
        kit.validate(self.request, self.response)

    def test_probability_keys_must_match(self):
        probs = self.response['answers']['department']['probabilities']
        probs['invented'] = probs.pop('other')
        self.invalid()

    def test_choice_not_in_criteria(self):
        self.response['answers']['department']['choice'] = 'PRIVATE_RAW_DATA'
        self.invalid()

    def test_choice_not_argmax(self):
        self.response['answers']['department']['choice'] = 'shipping'
        self.invalid()

    def test_choice_tied_argmax_is_structurally_valid(self):
        self.response['answers']['department']['probabilities'] = {
            'billing': 0.5, 'shipping': 0.5, 'returns': 0, 'unknown': 0, 'other': 0}
        kit.validate(self.request, self.response)

    def test_confidence_required_for_choice_and_score(self):
        for question in ('department', 'detail'):
            self.request, self.response = fixtures()
            del self.response['answers'][question]['confidence']
            self.invalid()

    def test_confidence_range(self):
        for bad in (True, -0.01, 1.01, float('inf'), float('nan')):
            self.response['answers']['detail']['confidence'] = bad
            self.invalid()

    def test_score_keys_are_exact_zero_based_indices(self):
        self.response['answers']['detail']['probabilities'] = {'0': 0, '1': 0.2, '02': 0.8}
        self.invalid()

    def test_score_expected_value(self):
        self.response['answers']['detail']['score'] = 1.7
        self.invalid()

    def test_score_values(self):
        for bad in (True, -1, 3, '1.8', float('nan')):
            self.response['answers']['detail']['score'] = bad
            self.invalid()

    def test_score_requires_two_to_ten_levels(self):
        self.request['questions']['detail']['criteria'] = ['Only one']
        self.invalid()

    def test_optional_legend_must_match_rubric(self):
        self.response['answers']['detail']['legend'] = {'0': 'No detail', '1': 'Partial detail', '2': 'Complete detail'}
        kit.validate(self.request, self.response)
        self.response['answers']['detail']['legend']['2'] = 'Conflicting rubric'
        self.invalid()

    def test_usage_required_nonnegative_integer(self):
        for bad in (True, -1, 1.5):
            self.response['usage']['input_tokens'] = bad
            self.invalid()
        del self.response['usage']
        self.invalid()

    def test_unknown_answer_fields_rejected(self):
        self.response['answers']['detail']['explanation'] = 'unsupported'
        self.invalid()

    def test_root_shapes(self):
        for bad in (None, [], 'text', 1):
            with self.assertRaises(kit.KitError):
                kit.validate(bad, self.response)
            with self.assertRaises(kit.KitError):
                kit.validate(self.request, bad)


def routing_policy():
    # SYNTHETIC/OFFLINE flags exercise logic; NOT actual approval/calibration.
    return {
        'mode': 'recommend', 'purpose': 'internal_ticket_routing', 'high_impact': False,
        'approved': True, 'approval_ref': 'SYNTHETIC/OFFLINE-TEST-ONLY',
        'calibrated': True, 'calibration_ref': 'SYNTHETIC/OFFLINE-TEST-ONLY',
        'pinned_model': 'jev-1.14.0',
        'thresholds': {'evidence_min': 0.9, 'department_probability_min': 0.9,
                       'department_confidence_min': 0.8, 'department_margin_min': 0.2}
    }


class GateTests(unittest.TestCase):
    def setUp(self):
        self.request, self.response = fixtures()
        self.policy = routing_policy()

    def test_shadow_is_default(self):
        self.assertTrue(hasattr(kit, 'gate'), 'gate missing')
        del self.policy['mode']
        result = kit.gate(self.request, self.response, self.policy)
        self.assertEqual(result['decision'], 'REVIEW')
        self.assertEqual(result['reason'], 'SHADOW_ONLY')
        self.assertIs(result['recommendation_only'], True)
        self.assertIs(result['action_executed'], False)
        self.assertIsNone(result['route'])

    def result(self):
        return kit.gate(self.request, self.response, self.policy)

    def hold(self):
        result = self.result()
        self.assertEqual(result['decision'], 'HOLD')
        self.assertIsNone(result['route'])
        self.assertIs(result['action_executed'], False)

    def test_recommendation_not_action(self):
        result = self.result()
        self.assertEqual(result['decision'], 'ROUTE_RECOMMENDATION')
        self.assertEqual(result['route'], 'billing')
        self.assertIs(result['recommendation_only'], True)
        self.assertIs(result['action_executed'], False)

    def test_malformed_response_holds(self):
        self.response['answers']['evidence_sufficient']['noul'] = True
        self.hold()

    def test_malformed_policy_holds(self):
        for value in (None, [], {}, 'bad'):
            self.policy = value
            self.hold()

    def test_missing_policy_field_holds(self):
        for key in routing_policy():
            if key == 'mode':
                continue
            with self.subTest(key=key):
                self.policy = routing_policy()
                del self.policy[key]
                self.hold()

    def test_high_impact_never_routes(self):
        self.policy['high_impact'] = True
        self.hold()

    def test_flags_require_real_bools(self):
        for key in ('high_impact', 'approved', 'calibrated'):
            for value in ('false', 0, 1, None):
                self.policy = routing_policy()
                self.policy[key] = value
                self.hold()

    def test_approval_required(self):
        self.policy['approved'] = False
        self.hold()

    def test_calibration_required(self):
        self.policy['calibrated'] = False
        self.hold()

    def test_refs_required(self):
        for key in ('approval_ref', 'calibration_ref'):
            self.policy = routing_policy()
            self.policy[key] = ' '
            self.hold()

    def test_thresholds_cannot_be_missing(self):
        self.policy['thresholds'] = {}
        self.hold()

    def test_thresholds_finite_bounded_nonbool(self):
        for key in routing_policy()['thresholds']:
            for value in (True, -0.01, 1.01, float('nan'), float('inf'), None, '0.9'):
                with self.subTest(key=key, value=value):
                    self.policy = routing_policy()
                    self.policy['thresholds'][key] = value
                    self.hold()

    def test_zero_thresholds_do_not_certify_uncertainty(self):
        self.policy['thresholds'] = {key: 0 for key in self.policy['thresholds']}
        self.hold()

    def test_model_alias_not_pinned(self):
        for value in ('jev-latest', 'jev-1.14', 'jev-1.14.0\n', 'other-1.14.0'):
            self.policy['pinned_model'] = value
            self.hold()

    def test_response_model_drift_holds(self):
        self.response['model'] = 'jev-1.13.0'
        self.hold()

    def test_request_alias_holds(self):
        self.request['model'] = 'jev-latest'
        self.hold()

    def test_non_internal_purpose_holds(self):
        self.policy['purpose'] = 'payment_execution'
        self.hold()

    def test_unknown_mode_holds(self):
        self.policy['mode'] = 'auto'
        self.hold()

    def test_missing_routing_question_holds(self):
        for key in ('evidence_sufficient', 'department'):
            self.request, self.response = fixtures()
            del self.request['questions'][key]
            del self.response['answers'][key]
            self.hold()

    def test_wrong_routing_question_type_holds(self):
        self.request['questions']['evidence_sufficient'] = {
            'type': 'choice', 'instructions': 'Enough?', 'criteria': {'yes': 'yes', 'no': 'no'}}
        self.response['answers']['evidence_sufficient'] = {
            'type': 'choice', 'choice': 'yes', 'probabilities': {'yes': 1, 'no': 0}, 'confidence': 1}
        self.hold()

    def test_unknown_and_other_review(self):
        for selected in ('unknown', 'other'):
            answer = self.response['answers']['department']
            answer['choice'] = selected
            answer['probabilities'] = {key: int(key == selected) for key in answer['probabilities']}
            result = self.result()
            self.assertEqual(result['decision'], 'REVIEW')
            self.assertIsNone(result['route'])

    def test_unknown_route_labels_not_echoed(self):
        criteria = self.request['questions']['department']['criteria']
        criteria['PRIVATE_RAW_DATA'] = criteria.pop('billing')
        answer = self.response['answers']['department']
        answer['choice'] = 'PRIVATE_RAW_DATA'
        answer['probabilities']['PRIVATE_RAW_DATA'] = answer['probabilities'].pop('billing')
        result = self.result()
        self.assertIn(result['decision'], ('HOLD', 'REVIEW'))
        self.assertNotIn('PRIVATE_RAW_DATA', str(result))

    def test_insufficient_evidence_review(self):
        self.response['answers']['evidence_sufficient']['noul'] = 0.5
        self.assertEqual(self.result()['decision'], 'REVIEW')

    def test_low_department_confidence_review(self):
        self.response['answers']['department']['confidence'] = 0.3
        self.assertEqual(self.result()['decision'], 'REVIEW')

    def test_low_probability_review(self):
        self.response['answers']['department']['probabilities'] = {
            'billing': 0.6, 'shipping': 0.4, 'returns': 0, 'unknown': 0, 'other': 0}
        self.assertEqual(self.result()['decision'], 'REVIEW')

    def test_tie_review_even_at_permissive_probability_threshold(self):
        self.policy['thresholds']['department_probability_min'] = 0.5
        self.response['answers']['department']['probabilities'] = {
            'billing': 0.5, 'shipping': 0.5, 'returns': 0, 'unknown': 0, 'other': 0}
        self.assertEqual(self.result()['decision'], 'REVIEW')

    def test_threshold_equality_passes(self):
        self.response['answers']['evidence_sufficient']['noul'] = 0.9
        self.response['answers']['department']['confidence'] = 0.8
        self.assertEqual(self.result()['decision'], 'ROUTE_RECOMMENDATION')

    def test_strictly_below_threshold_reviews(self):
        self.response['answers']['evidence_sufficient']['noul'] = 0.899999999
        self.assertEqual(self.result()['decision'], 'REVIEW')


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.offline-test-', dir=MODULE.parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        request, response = fixtures()
        for name, value in (('request.json', request), ('response.json', response), ('policy.json', routing_policy())):
            (self.root / name).write_text(json.dumps(value), encoding='utf-8')

    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-B', str(MODULE), *map(str, args)],
                              cwd=self.root, text=True, capture_output=True, timeout=10)

    def arguments(self):
        return ['--request', self.root / 'request.json', '--response', self.root / 'response.json']

    def test_cli_validate(self):
        result = self.run_cli('validate', *self.arguments())
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.strip(), 'CLI output missing')
        self.assertEqual(json.loads(result.stdout)['valid'], True)
        self.assertEqual(result.stderr, '')

    def test_cli_gate_recommendation(self):
        result = self.run_cli('gate', *self.arguments(), '--policy', self.root / 'policy.json')
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.strip(), 'CLI output missing')
        self.assertEqual(json.loads(result.stdout)['decision'], 'ROUTE_RECOMMENDATION')

    def test_cli_invalid_json_holds_sanitized(self):
        (self.root / 'response.json').write_text('PRIVATE_RAW_DATA', encoding='utf-8')
        result = self.run_cli('gate', *self.arguments(), '--policy', self.root / 'policy.json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['decision'], 'HOLD')
        self.assertNotIn('PRIVATE_RAW_DATA', result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')

    def test_cli_missing_file(self):
        result = self.run_cli('gate', *self.arguments(), '--policy', self.root / 'PRIVATE_RAW_DATA')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['decision'], 'HOLD')
        self.assertNotIn('PRIVATE_RAW_DATA', result.stdout + result.stderr)

    def test_cli_argument_errors_sanitized(self):
        result = self.run_cli('gate', '--PRIVATE_RAW_DATA')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('PRIVATE_RAW_DATA', result.stdout + result.stderr)

    def test_cli_duplicate_keys_holds(self):
        (self.root / 'policy.json').write_text('{"mode":"shadow","mode":"recommend"}', encoding='utf-8')
        result = self.run_cli('gate', *self.arguments(), '--policy', self.root / 'policy.json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['decision'], 'HOLD')

    def test_cli_invalid_validate_exit(self):
        (self.root / 'response.json').write_text('{}', encoding='utf-8')
        result = self.run_cli('validate', *self.arguments())
        self.assertEqual(result.returncode, 2)
        self.assertIs(json.loads(result.stdout)['valid'], False)

    def test_cli_input_size_limit(self):
        (self.root / 'response.json').write_text(' ' * (1024 * 1024 + 1), encoding='utf-8')
        result = self.run_cli('validate', *self.arguments())
        self.assertEqual(result.returncode, 2)

    def test_cli_deeply_nested_json(self):
        (self.root / 'response.json').write_text('[' * 1500 + '0' + ']' * 1500, encoding='utf-8')
        result = self.run_cli('gate', *self.arguments(), '--policy', self.root / 'policy.json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, '')
        self.assertEqual(json.loads(result.stdout)['decision'], 'HOLD')

    def test_init_creates_usable_shadow_scaffolding(self):
        out = self.root / 'new' / 'nested'
        result = self.run_cli('init', '--out', out)
        self.assertEqual(result.returncode, 0)
        self.assertTrue((out / 'design.md').is_file(), 'init did not create design.md')
        expected = {'design.md', 'rubric.json', 'policy.json', 'request.json', 'response.synthetic.json'}
        self.assertEqual({path.name for path in out.iterdir()}, expected)
        validation = self.run_cli('validate', '--request', out / 'request.json',
                                  '--response', out / 'response.synthetic.json')
        self.assertEqual(validation.returncode, 0)
        gated = self.run_cli('gate', '--request', out / 'request.json',
                             '--response', out / 'response.synthetic.json', '--policy', out / 'policy.json')
        self.assertEqual(gated.returncode, 3)
        self.assertEqual(json.loads(gated.stdout)['decision'], 'REVIEW')
        policy = json.loads((out / 'policy.json').read_text(encoding='utf-8'))
        self.assertIs(policy['approved'], False)
        self.assertIs(policy['calibrated'], False)
        self.assertTrue(all(v is None for v in policy['thresholds'].values()))
        memo = (out / 'design.md').read_text(encoding='utf-8')
        for keyword in ('provider', 'model', 'risk', 'state', 'rights', 'eval', 'rollback'):
            self.assertIn(keyword, memo)

    def test_init_collision_does_not_overwrite_or_partially_add(self):
        out = self.root / 'existing'
        out.mkdir()
        (out / 'policy.json').write_text('KEEP', encoding='utf-8')
        result = self.run_cli('init', '--out', out)
        self.assertEqual(result.returncode, 2)
        self.assertEqual((out / 'policy.json').read_text(encoding='utf-8'), 'KEEP')
        self.assertEqual({p.name for p in out.iterdir()}, {'policy.json'})

    def test_init_preserves_unrelated_files(self):
        out = self.root / 'existing'
        out.mkdir()
        (out / 'unrelated.txt').write_text('KEEP', encoding='utf-8')
        result = self.run_cli('init', '--out', out)
        self.assertEqual(result.returncode, 0)
        self.assertEqual((out / 'unrelated.txt').read_text(encoding='utf-8'), 'KEEP')
        self.assertTrue((out / 'request.json').is_file())

    def test_init_symlink_parent_rejected(self):
        target = self.root / 'target'
        target.mkdir()
        link = self.root / 'link'
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('symlink privilege unavailable on this platform')
        result = self.run_cli('init', '--out', link / 'child')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(list(target.iterdir()), [])

    def test_offline_gate_under_runtime_audit_guard(self):
        probe = (
            "import sys, runpy\n"
            "def guard(event, args):\n"
            "    if event.startswith(('socket.', 'urllib.', 'http.client.', 'subprocess.')) or event in "
            "('os.system', 'os.posix_spawn', 'os.spawn', 'os.exec'):\n"
            "        raise RuntimeError('FORBIDDEN_EXTERNAL_ACTION')\n"
            "sys.addaudithook(guard)\n"
            "sys.argv = sys.argv[1:]\n"
            "runpy.run_path(sys.argv[0], run_name='__main__')\n"
        )
        result = subprocess.run([sys.executable, '-B', '-c', probe, str(MODULE), 'gate',
                                 *map(str, self.arguments()), '--policy', str(self.root / 'policy.json')],
                                cwd=self.root, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['decision'], 'ROUTE_RECOMMENDATION')


class SafetyRegressionTests(unittest.TestCase):
    def test_source_has_only_allowlisted_stdlib_imports(self):
        tree = ast.parse(MODULE.read_text(encoding='utf-8'))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'eval', 'exec', '__import__', 'compile'})
        self.assertEqual(imports, {'argparse', 'json', 'math', 'pathlib', 're'})

    def test_fallback_criteria_required_for_recommendation(self):
        request, response = fixtures()
        for name in ('unknown', 'other'):
            del request['questions']['department']['criteria'][name]
            del response['answers']['department']['probabilities'][name]
        response['answers']['department']['probabilities']['billing'] = 0.98
        self.assertEqual(kit.gate(request, response, routing_policy())['decision'], 'HOLD')

    def test_margin_gate_independent_of_probability_and_confidence(self):
        request, response = fixtures()
        policy = routing_policy()
        policy['thresholds']['department_margin_min'] = 0.96
        self.assertEqual(kit.gate(request, response, policy)['decision'], 'REVIEW')

    def test_shadow_still_rejects_malformed_response(self):
        request, response = fixtures()
        policy = routing_policy()
        policy['mode'] = 'shadow'
        response['answers']['detail']['probabilities']['0'] = True
        self.assertEqual(kit.gate(request, response, policy)['decision'], 'HOLD')

    def test_score_sum_tolerance_is_not_a_score_consistency_bypass(self):
        request, response = fixtures()
        response['answers']['detail']['probabilities']['0'] = 0.0000005
        kit.validate(request, response)
        response['answers']['detail']['score'] = 1.80001
        with self.assertRaises(kit.KitError):
            kit.validate(request, response)

    def test_every_json_node_hostile_type_replacements_fail_closed_without_crash(self):
        roots = [*fixtures(), routing_policy()]
        def paths(value, path=()):
            yield path
            if isinstance(value, dict):
                for key, child in value.items():
                    yield from paths(child, path + (key,))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    yield from paths(child, path + (index,))
        for index, root in enumerate(roots):
            for path in paths(root):
                for value in (None, True, [], {}, '', 'PRIVATE_RAW_DATA', -1, 10**400, float('nan')):
                    changed = copy.deepcopy(roots)
                    if path:
                        node = changed[index]
                        for key in path[:-1]:
                            node = node[key]
                        node[path[-1]] = value
                    else:
                        changed[index] = value
                    result = kit.gate(*changed)
                    self.assertIn(result['decision'], ('HOLD', 'REVIEW', 'ROUTE_RECOMMENDATION'))
                    self.assertIs(result['action_executed'], False)
                    self.assertNotIn('PRIVATE_RAW_DATA', json.dumps(result))


if __name__ == "__main__":
    unittest.main()
