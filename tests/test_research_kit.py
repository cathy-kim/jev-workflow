"""Offline synthetic contracts; never upstream models or media."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).absolute().parents[1]
TOOL = ROOT / "plugins/jev/skills/jev-decisions/scripts/research_kit.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("research_kit", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlanTests(unittest.TestCase):
    def test_every_task_selects_only_an_unverified_candidate(self):
        self.assertTrue(TOOL.is_file(), "offline research CLI is not implemented")
        kit = load_tool()
        tasks = {
            "video-grounding": "videojev", "video-choice": "videojev",
            "spatial-choice": "mjev-spatial", "spatial-scalar": "mjev-spatial",
            "spatial-point": "mjev-spatial", "text-choice": "jeva",
            "text-noul": "jeva", "text-score": "jeva",
        }
        for task, backend in tasks.items():
            with self.subTest(task=task), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(kit.main(["plan", "--task", task]), 0)
                report = json.loads(out.getvalue())
                self.assertEqual(report["candidate_backend"], backend)
                self.assertEqual(report["runtime_status"], "UNVERIFIED")
                self.assertFalse(report["actual_execution"])
                self.assertFalse(report["model_loaded"])
                self.assertTrue(report["advisory_only"])
                self.assertTrue(report["supported_input_shape"])
                self.assertTrue(report["limits"])
                self.assertEqual(report["readiness"], "BLOCKED_SOURCE_ISSUES"
                                 if backend == "mjev-spatial" else "CONTRACT_ONLY")


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.kit = load_tool()

    def invoke(self, backend, value=None, raw=None):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="jev-contract-") as directory:
            path = Path(directory) / "request.json"
            path.write_bytes(raw if raw is not None else json.dumps(value).encode())
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = self.kit.main(["validate", "--backend", backend, "--input", str(path)])
            report = json.loads(out.getvalue())
        self.assertFalse(report["actual_execution"])
        self.assertFalse(report["model_loaded"])
        self.assertTrue(report["advisory_only"])
        return code, report

    def valid(self, backend, value):
        code, report = self.invoke(backend, value)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["status"], "VALID_CONTRACT_ONLY")
        self.assertNotIn("prediction", report)
        return report

    def invalid(self, backend, value=None, raw=None):
        code, report = self.invoke(backend, value, raw)
        self.assertEqual(code, 2, report)
        self.assertEqual(report["status"], "INVALID_CONTRACT")
        return report

    def test_video_questions_are_input_only_with_explicit_ids(self):
        rows = [{"id": "g", "task": "grounding", "query": "Synthetic event."},
                {"id": "c", "task": "choice", "query": "Synthetic question?",
                 "options": ["same", "same"]}]
        self.valid("videojev", rows)
        bad = [[], {}, rows + [rows[0]], [dict(rows[0], id=True)],
               [{k: v for k, v in rows[0].items() if k != "id"}],
               [dict(rows[0], spans=[[0, 1]])], [dict(rows[0], options=["x", "y"])],
               [dict(rows[0], task="score")], [dict(rows[0], query="<|decide|>")],
               [dict(rows[1], options=["only"])], [dict(rows[1], options="ab")],
               [dict(rows[1], options=["a", " "])], [dict(rows[1], answer_index=0)]]
        for value in bad:
            with self.subTest(value=value):
                self.invalid("videojev", value)


    def test_spatial_single_object_choice_scalar_and_point(self):
        import copy
        def request(space):
            return {"id": "synthetic", "input": {
                "media": [{"kind": "image", "uri": "images/synthetic.png"}],
                "question": "Synthetic: clockwise from image up?",
                "answer_space": space}}
        spaces = [
            {"kind": "choice", "options": [{"id": "l", "text": "left"}, {"id": "r", "text": "right"}]},
            {"kind": "scalar", "quantity": "distance", "unit": "m"},
            {"kind": "scalar", "quantity": "count", "unit": "count"},
            {"kind": "scalar", "quantity": "angle", "unit": "deg", "angle_semantics": "clockwise from image up"},
            {"kind": "point", "coordinate_system": "normalized_xy", "num_points": 1},
        ]
        for space in spaces:
            with self.subTest(space=space):
                result = self.valid("mjev-spatial", request(space))
                self.assertEqual(result["readiness"], "BLOCKED_SOURCE_ISSUES")
        bad_spaces = [
            dict(spaces[0], options=spaces[0]["options"][:1]),
            dict(spaces[0], options=[spaces[0]["options"][0]] * 2),
            dict(spaces[0], options=spaces[0]["options"] * 17),
            dict(spaces[1], unit="cm"), dict(spaces[1], quantity=""),
            dict(spaces[2], quantity="distance"),
            {"kind": "scalar", "quantity": "angle", "unit": "deg"},
            dict(spaces[3], angle_semantics="counterclockwise from camera north"),
            dict(spaces[3], angle_semantics=True), dict(spaces[1], value=1),
            dict(spaces[4], coordinate_system="pixels"),
            dict(spaces[4], num_points=True), dict(spaces[4], num_points=1.0),
            dict(spaces[4], num_points=2), dict(spaces[4], points=[[0.5, 0.5]]),
        ]
        for space in bad_spaces:
            with self.subTest(space=space):
                self.invalid("mjev-spatial", request(space))
        base = request(spaces[4])
        for bad in ([base], base["input"], dict(base, target={"points": [[0, 1]]}),
                    dict(base, sample_id="another"), dict(base, id=False)):
            self.invalid("mjev-spatial", bad)
        for images in ([], base["input"]["media"] * 2):
            bad = copy.deepcopy(base)
            bad["input"]["media"] = images
            self.invalid("mjev-spatial", bad)
        for uri in ("https://example.invalid/x.png", "file:///x.png", "../x.png",
                    "/x.png", "a/../x.png", "a/./x.png", "a//x.png", "a\\\\x.png",
                    "C:/x.png", "a/%2e%2e/x.png", "~/x.png", "a/x.png?key=secret",
                    "a/\u0000.png", "a/\uff0e\uff0e/x.png"):
            bad = copy.deepcopy(base)
            bad["input"]["media"][0]["uri"] = uri
            with self.subTest(uri=uri):
                self.invalid("mjev-spatial", bad)


    def test_jeva_raw_predict_kwargs_not_evaluation_labels(self):
        base = {"state": {"evidence": ["synthetic", None, True, 2]},
                "question": "Synthetic question?", "decision_type": "choice",
                "options": ["same", "same"], "allow_null": True}
        self.valid("jeva", base)
        self.valid("jeva", dict(base, state="", values=None, positive_index=1))
        noul = dict(base, decision_type="noul", allow_null=False, positive_index=0)
        score = dict(base, decision_type="score", allow_null=False, values=[2, -1])
        self.valid("jeva", noul)
        self.valid("jeva", dict(noul, positive_index=1))
        self.valid("jeva", score)  # inference permits non-monotone values
        for bad in ([base], dict(base, id="label"), dict(base, target_probs=[0, 1, 0]),
                    dict(base, unknown="PRIVATE_SENTINEL"), dict(base, options=["x"]),
                    dict(base, options="ab"), dict(base, allow_null=1),
                    dict(base, positive_index=True), dict(base, positive_index=0),
                    dict(base, values=[1, 2]), dict(base, question=" "),
                    dict(base, decision_type=[]), dict(noul, allow_null=True),
                    dict(noul, positive_index=True), dict(noul, positive_index=1.0),
                    dict(noul, positive_index=-1), dict(noul, positive_index=2),
                    {k: v for k, v in noul.items() if k != "positive_index"},
                    dict(noul, options=["a", "b", "c"]),
                    dict(score, allow_null=True), dict(score, values=None),
                    {k: v for k, v in score.items() if k != "values"},
                    dict(score, values=[True, 1]), dict(score, values=[1]),
                    dict(score, values=["0", "1"]),
                    dict(score, values=[1e13, 0]), dict(score, values=[float("inf"), 0]),
                    dict(score, values=[float("nan"), 0])):
            with self.subTest(bad=bad):
                self.invalid("jeva", bad)


    def test_strict_json_and_bounded_reader(self):
        base = b'{"state":"synthetic","question":"Q?","decision_type":"choice","options":["a","b"],"allow_null":false}'
        self.valid("jeva", json.loads(base))
        bad = [b'', b'\xff', base + b'{}', b'{}\n{}',
               base.replace(b'"state":"synthetic"', b'"state":"first","state":"second"'),
               base.replace(b'"synthetic"', b'{"x":1,"x":2}'),
               base.replace(b'"synthetic"', b'"\\ud800"'),
               base.replace(b'"synthetic"', b'"\\u0000"'),
               base.replace(b'"synthetic"', b'NaN'),
               base.replace(b'"synthetic"', b'Infinity'),
               base.replace(b'"synthetic"', b'-Infinity'),
               base.replace(b'"synthetic"', b'1e999'),
               base.replace(b'"synthetic"', b'9' * 400),
               base.replace(b'"synthetic"', b'[' * 40 + b'0' + b']' * 40),
               b'[' * 2000 + b'0' + b']' * 2000]
        for raw in bad:
            with self.subTest(raw_prefix=raw[:80]):
                self.invalid("jeva", raw=raw)
        cap = 1024 * 1024
        code, report = self.invoke("jeva", raw=base + b' ' * (cap - len(base)))
        self.assertEqual(code, 0, report)
        report = self.invalid("jeva", raw=base + b' ' * (cap + 1 - len(base)))
        self.assertEqual(report["error_code"], "INPUT_TOO_LARGE")

    def test_reader_reads_only_limit_plus_one_in_binary(self):
        from unittest import mock
        original_open = open
        reads = []
        def bounded_open(*args, **kwargs):
            self.assertEqual(args[1], "rb")
            stream = original_open(*args, **kwargs)
            wrapper = mock.MagicMock(wraps=stream)
            wrapper.__enter__.return_value = wrapper
            wrapper.__exit__.side_effect = lambda *unused: stream.close()
            def read(size=-1):
                reads.append(size)
                self.assertEqual(size, 1024 * 1024 + 1)
                return stream.read(size)
            wrapper.read.side_effect = read
            return wrapper
        with mock.patch.object(self.kit, "open", bounded_open, create=True):
            self.invalid("videojev", raw=b'{}')
        self.assertEqual(reads, [1024 * 1024 + 1])

    def test_errors_never_echo_sensitive_values_or_input_path(self):
        secret = "PRIVATE_SENTINEL_DO_NOT_ECHO"
        report = self.invalid("videojev", [{"id": secret, "task": "grounding", "query": secret, secret: secret}])
        self.assertNotIn(secret, json.dumps(report))
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = self.kit.main(["validate", "--backend", "jeva", "--input", "/missing/" + secret + ".json"])
        self.assertEqual(code, 2)
        self.assertNotIn(secret, out.getvalue() + err.getvalue())
        for argv in (["validate", "--backend", secret, "--input", secret],
                     ["plan", "--task", secret], ["--unknown", secret]):
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
                code = self.kit.main(argv)
            self.assertEqual(code, 2)
            self.assertNotIn(secret, out.getvalue() + err.getvalue())

    def test_field_budgets_and_malformed_shapes(self):
        base = {"state": "synthetic", "question": "Q?", "decision_type": "choice",
                "options": ["a", "b"], "allow_null": False}
        for value in (dict(base, question="x" * 16385), dict(base, state="x" * 65537),
                      dict(base, options=["x"] * 257),
                      dict(base, state=[0] * 20001)):
            self.invalid("jeva", value)
        for backend in ("videojev", "mjev-spatial", "jeva"):
            for value in (None, True, 3, "x", [None], {"input": None}):
                with self.subTest(backend=backend, shape=type(value).__name__):
                    self.invalid(backend, value)


    def test_duplicate_keys_at_every_backend_boundary(self):
        inputs = {
            "videojev": b'[{"id":"a","task":"grounding","query":"x","query":"y"}]',
            "mjev-spatial": b'{"id":"a","id":"b","input":{}}',
            "jeva": b'{"state":{"nested":1,"nested":2}}',
        }
        for backend, raw in inputs.items():
            with self.subTest(backend=backend):
                self.assertEqual(self.invalid(backend, raw=raw)["error_code"], "DUPLICATE_JSON_KEY")

    def test_real_cli_exit_codes_and_version(self):
        import subprocess
        import sys
        version = subprocess.run([sys.executable, "-I", "-B", str(TOOL), "--version"],
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual(version.returncode, 0)
        self.assertEqual(version.stdout.strip(), "1.1.0")
        for args, expected in ((["plan", "--task", "text-choice"], 0),
                               (["plan", "--task", "bogus"], 2),
                               (["validate", "--backend", "jeva", "--input", "missing.json"], 2)):
            run = subprocess.run([sys.executable, "-I", "-B", str(TOOL), *args],
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, expected)
            self.assertFalse(json.loads(run.stdout)["actual_execution"])
            self.assertEqual(run.stderr, "")

    def test_explicit_input_symlink_and_nonregular_are_rejected(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory(prefix="jev-file-policy-") as directory:
            root = Path(directory)
            request = root / "request.json"
            request.write_text("{}", encoding="utf-8")
            link = root / "link.json"
            link.symlink_to(request)
            folder = root / "folder.json"
            folder.mkdir()
            fifo = root / "pipe.json"
            os.mkfifo(fifo)
            for path in (link, folder, fifo, root / "model.safetensors", root / ".env"):
                with self.subTest(name=path.name), contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(self.kit.main(["validate", "--backend", "jeva", "--input", str(path)]), 2)
                    self.assertEqual(json.loads(out.getvalue())["status"], "INVALID_CONTRACT")

    def test_audit_denies_network_process_and_all_unselected_file_opens(self):
        import subprocess
        import sys
        import tempfile
        # The harness launches Python, but the tool runs INSIDE the audit fence.
        # Read only our script before exec; imports and every tool operation are audited.
        harness = r'''
import argparse, contextlib, io, json, locale, os, re, socket, stat, subprocess, sys
from unittest import mock
# Prime stdlib parser imports, not the tool or any upstream module.
argparse.ArgumentParser(prog="audit-prime")
tool, request, backend = sys.argv[1:]
with open(tool, "rb") as stream:
    code = compile(stream.read(), "research_kit_under_audit", "exec")
violations = []
def audit(event, args):
    if event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn", "os.fork")) or event == "os.system":
        violations.append(event)
        raise RuntimeError("AUDIT_DENIED")
    if event == "open":
        path, mode, flags = args
        if path != request or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
            violations.append("unselected_open")
            raise RuntimeError("AUDIT_DENIED")
sys.addaudithook(audit)
# Positive controls: the fence really denies these, rather than silently missing events.
for operation in (lambda: socket.socket(),
                  lambda: subprocess.Popen([sys.executable, "-c", "raise SystemExit(99)"]),
                  lambda: open("/never-read/credentials/.env", "rb")):
    try:
        operation()
    except RuntimeError:
        pass
    else:
        raise AssertionError("audit fence not effective")
assert len(violations) == 3
violations.clear()
sys.argv = ["research_kit", "validate", "--backend", backend, "--input", request]
# argparse/gettext probes only its stdlib locale directory; media probes stay denied.
original_stat = os.stat
def guarded_stat(path, *args, **kwargs):
    if str(path).startswith(sys.base_prefix + os.sep):
        return original_stat(path, *args, **kwargs)
    raise AssertionError("unexpected filesystem probe")
def deny_probe(*args, **kwargs):
    raise AssertionError("unexpected filesystem probe")
with mock.patch("os.stat", guarded_stat), mock.patch("os.lstat", deny_probe), mock.patch("os.readlink", deny_probe):
    namespace = {"__name__": "research_kit_audited"}
    exec(code, namespace)
    for task in namespace["TASKS"]:
        with contextlib.redirect_stdout(io.StringIO()) as output:
            assert namespace["main"](["plan", "--task", task]) == 0
        assert json.loads(output.getvalue())["status"] == "PLAN_ONLY"
    assert namespace["main"](sys.argv[1:]) == 0
assert not violations, violations
'''
        fixtures = {
            "videojev": [{"id": "g", "task": "grounding", "query": "Synthetic event"}],
            "mjev-spatial": {"id": "p", "input": {
                "media": [{"kind": "image", "uri": "media.png"}], "question": "Synthetic point?",
                "answer_space": {"kind": "point", "num_points": 1, "coordinate_system": "normalized_xy"}}},
            "jeva": {"state": "synthetic", "question": "Q?", "decision_type": "score",
                     "options": ["low", "high"], "values": [0, 1], "allow_null": False},
        }
        with tempfile.TemporaryDirectory(prefix="jev-audit-") as directory:
            root = Path(directory)
            # A referenced symlink must remain opaque: no resolve, existence or content check.
            (root / "media.png").symlink_to(root / "never-created-secret")
            for backend, fixture in fixtures.items():
                request = root / "request.json"
                request.write_text(json.dumps(fixture), encoding="utf-8")
                run = subprocess.run([sys.executable, "-I", "-B", "-c", harness,
                                      str(TOOL), str(request), backend],
                                     capture_output=True, text=True, timeout=15, cwd=directory)
                with self.subTest(backend=backend):
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(json.loads(run.stdout)["status"], "VALID_CONTRACT_ONLY")

    def test_synthetic_demo_runs_actual_cli_and_checks_failures(self):
        import subprocess
        import sys
        demo = ROOT / "examples/research_demo.py"
        self.assertTrue(demo.is_file(), "synthetic subprocess demo is missing")
        run = subprocess.run([sys.executable, "-I", "-B", str(demo)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(run.stdout)
        self.assertTrue(report["synthetic_input_only"])
        self.assertFalse(report["actual_execution"])
        self.assertEqual(len(report["checks"]), 19)
        self.assertTrue(all(row["returncode"] == row["expected_returncode"] for row in report["checks"]))


if __name__ == "__main__":
    unittest.main()
