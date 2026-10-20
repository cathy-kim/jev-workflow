"""Run synthetic offline CLI cases and verify real subprocess exit codes.

Run from any working directory: python3 /path/to/checkout/examples/offline_demo.py
No model, network, credentials, package installation or downstream actions.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'plugins/jev/skills/jev-decisions/scripts/decision_kit.py'
FIXTURES = SCRIPT.parent / 'examples'


def run_case(command, expected_exit, expected=None):
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *map(str, command)],
                            capture_output=True, text=True, timeout=15)
    if result.returncode != expected_exit or result.stderr:
        raise RuntimeError('Unexpected CLI exit or stderr')
    output = json.loads(result.stdout)
    for key, value in (expected or {}).items():
        if output.get(key) != value:
            raise RuntimeError('Unexpected CLI outcome')
    if 'decision' in output:
        if output.get('recommendation_only') is not True or output.get('action_executed') is not False:
            raise RuntimeError('Recommendation-only invariant violated')
    return {'exit_code': result.returncode, 'output': output}


def main():
    report = {'synthetic_only': True, 'external_calls': False}
    with tempfile.TemporaryDirectory(prefix='jev-offline-demo-') as temporary:
        # Resolve platform temporary-directory aliases before init's symlink check.
        out = Path(temporary).resolve() / 'generated'
        report['init'] = run_case(['init', '--out', out], 0, {'offline_only': True})
        args = ['--request', out / 'request.json', '--response', out / 'response.synthetic.json']
        report['validate'] = run_case(['validate', *args], 0, {'valid': True})
        report['shadow'] = run_case(['gate', *args, '--policy', out / 'policy.json'],
                                  3, {'decision': 'REVIEW', 'reason': 'SHADOW_ONLY'})
        report['recommend'] = run_case(['gate', *args, '--policy', FIXTURES / 'policy.synthetic-recommend.json'],
                                     0, {'decision': 'ROUTE_RECOMMENDATION', 'route': 'billing'})
        report['high_impact'] = run_case(['gate', *args, '--policy', FIXTURES / 'policy.synthetic-high-impact.json'],
                                       2, {'decision': 'HOLD', 'reason': 'HIGH_IMPACT'})
        report['malformed'] = run_case(['gate', '--request', out / 'request.json',
                                       '--response', FIXTURES / 'response.malformed.synthetic.json',
                                       '--policy', out / 'policy.json'],
                                      2, {'decision': 'HOLD', 'reason': 'INVALID_JSON'})
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
