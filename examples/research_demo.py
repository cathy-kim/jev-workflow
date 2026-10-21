#!/usr/bin/env python3
"""Run synthetic input-only examples through our offline CLI, not upstream code.

No media is created or opened. The image URI is an intentionally nonexistent
lexical reference. Successful checks are NOT model predictions, live readiness,
media provenance, semantic evaluation, or reproduction of paper results.
"""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).absolute().parents[1]
TOOL = ROOT / "plugins/jev/skills/jev-decisions/scripts/research_kit.py"


def synthetic_requests():
    def spatial(space):
        return {"id": "synthetic-spatial", "input": {
            "media": [{"kind": "image", "uri": "synthetic/not-created.png"}],
            "question": "Synthetic spatial schema example, not observed evidence.",
            "answer_space": space}}

    def jeva(kind, **kwargs):
        return {"state": "SYNTHETIC INPUT ONLY: no factual evidence or prediction.",
                "question": "Synthetic contract question?", "decision_type": kind,
                "options": ["Synthetic option A", "Synthetic option B"],
                "allow_null": False, **kwargs}

    return {
        "video-grounding": ("videojev", [
            {"id": "synthetic-g", "task": "grounding", "query": "Synthetic event description."}]),
        "video-choice": ("videojev", [
            {"id": "synthetic-c", "task": "choice", "query": "Synthetic question?",
             "options": ["Synthetic A", "Synthetic B"]}]),
        "spatial-choice": ("mjev-spatial", spatial({"kind": "choice", "options": [
            {"id": "a", "text": "Synthetic left"}, {"id": "b", "text": "Synthetic right"}]})),
        "spatial-scalar": ("mjev-spatial", spatial({"kind": "scalar", "quantity": "distance", "unit": "m"})),
        "spatial-point": ("mjev-spatial", spatial({"kind": "point", "coordinate_system": "normalized_xy", "num_points": 1})),
        "text-choice": ("jeva", jeva("choice", allow_null=True)),
        "text-noul": ("jeva", jeva("noul", positive_index=1)),
        "text-score": ("jeva", jeva("score", values=[0, 2])),
    }


def run_check(label, args, expected_code, expected_status):
    result = subprocess.run([sys.executable, "-I", "-B", str(TOOL), *args],
                            capture_output=True, text=True, timeout=10, check=False)
    # Never print subprocess stderr, which could contain paths after an interpreter failure.
    if result.returncode != expected_code or result.stderr:
        raise RuntimeError("Synthetic CLI check failed (exit/stderr)")
    report = json.loads(result.stdout)
    if (report.get("status") != expected_status or report.get("actual_execution") is not False
            or report.get("model_loaded") is not False or report.get("advisory_only") is not True):
        raise RuntimeError("Synthetic CLI check failed (metadata)")
    return {"check": label, "returncode": result.returncode,
            "expected_returncode": expected_code, "status": report["status"],
            "readiness": report["readiness"]}


def main():
    checks = []
    with TemporaryDirectory(prefix="jev-synthetic-research-") as directory:
        path = Path(directory) / "synthetic-request.json"
        for task, (backend, request) in synthetic_requests().items():
            checks.append(run_check(task + ":plan", ["plan", "--task", task], 0, "PLAN_ONLY"))
            path.write_text(json.dumps(request, ensure_ascii=True, allow_nan=False), encoding="utf-8")
            checks.append(run_check(task + ":valid", ["validate", "--backend", backend,
                                                       "--input", str(path)], 0, "VALID_CONTRACT_ONLY"))
        invalid = {
            "videojev": [{"id": "synthetic", "task": "choice", "query": "Q?", "options": ["only one"]}],
            "mjev-spatial": {"id": "synthetic", "input": {}, "target": {"value": 0}},
            "jeva": {"state": "synthetic", "question": "Q?", "decision_type": "noul",
                     "options": ["no", "yes"], "positive_index": True, "allow_null": False},
        }
        for backend, request in invalid.items():
            path.write_text(json.dumps(request), encoding="utf-8")
            checks.append(run_check(backend + ":invalid", ["validate", "--backend", backend,
                                                            "--input", str(path)], 2, "INVALID_CONTRACT"))
    print(json.dumps({"synthetic_input_only": True, "actual_execution": False,
                      "model_loaded": False, "advisory_only": True, "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
