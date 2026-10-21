# Research models: select, validate, then evaluate

These independent research projects are **not TypeSafe API model IDs**. Reading their papers or validating an input does not install a model, enable a modality, reproduce a benchmark, or authorize execution. This toolkit supplies references and an **offline contract planner/validator**, not an inference adapter.

The accompanying source reviews cover complete paper text and appendices, pinned implementation call graphs, training/evaluation differences, licensing and resource limits. Their experiments remain author-reported, not locally reproduced. Each review records its exact reading and visual-inspection scope.

## Select by task

| Need | Candidate | Critical boundary |
| --- | --- | --- |
| Find one described event interval in a video | [VideoJev](videojev.md) | A returned interval is not proof of event presence. Released HF inference is Joint plus vision-feature reuse, not the separate research KV-cache path. |
| Select among supplied video answers | [VideoJev](videojev.md) | Preserve options and query order; no free-form answer, native audio, streaming, or execution guarantee. |
| Image-grounded spatial relation, meter/count/degree estimate, single normalized point | [MJev-Spatial](mjev-spatial.md) | Runtime promotion blocked pending dependency, API/export, checkpoint-saving and checkpoint-provenance resolution. No clicks or robot actions. |
| Text Choice/Noul/Score, candidate absence, reusable option sets | [Jeva](jeva.md) | Standalone local model. Conditional competition, joint mass and null are different; cache requires fixed model/tokenizer/settings. |
| Existing TypeSafe / DeepEval workflow | Existing verified adapter | Do not replace a functioning provider based on similar names or unrelated paper metrics. |

## Use the shipped offline tool

Resolve these paths relative to this skill directory. Commands do not import upstream model packages, download weights, open referenced media, read credentials, or call a provider.

```bash
python3 scripts/research_kit.py plan --task video-grounding
python3 scripts/research_kit.py plan --task spatial-point
python3 scripts/research_kit.py plan --task text-choice
python3 scripts/research_kit.py validate --backend videojev --input questions.json
python3 scripts/research_kit.py validate --backend mjev-spatial --input spatial-request.json
python3 scripts/research_kit.py validate --backend jeva --input decision-request.json
```

The planner's other tasks are `video-choice`, `spatial-choice`, `spatial-scalar`, `text-noul`, and `text-score`. Planning selects a research candidate; **it never activates inference**. Validation success means `VALID_CONTRACT_ONLY`, not safe media, model accuracy, available hardware, or production readiness. The tool's strict subset can reject inputs an upstream entrypoint accepts. Inspect `--help` and the detailed references before adapting an existing dataset.

Input shapes:

- VideoJev: a list of questions with explicit unique `id`, `task`, `query`, and choice `options`. It is not a labeled training manifest or a video-file loader.
- MJev-Spatial: an input request using the upstream `media`, `question`, and `answer_space` structure; supported wrapper details and constraints are documented by the tool. Media URIs are only validated as local relative path strings, never opened.
- Jeva: raw `predict` argument shape: `state`, `question`, `decision_type`, `options`, `allow_null`, plus explicit task-specific `values` or `positive_index`. It is not TypeSafe JSON and does not accept targets or evaluation labels as model input.

## Agent workflow

1. Identify the requested modality, answer space and consequence of a wrong answer. Read the matching full reference before constructing a request or recommending a runtime.
2. Use `plan` to make the candidate and blockers explicit. Validate a synthetic or explicitly authorized request with the offline tool; do not publish private input/output in a report or PR.
3. Keep permissions, file access, schema checks, units, bounds, stable IDs, score arithmetic and tool execution in ordinary code. Never infer authorization from a model score, point, interval or null outcome.
4. For a real backend, separately establish code/weight/base revisions, license notices, dependency compatibility, runtime, data rights and compute budget. Repair source blockers in a separately scoped implementation, not silently in a user's environment.
5. Implement a bounded adapter only after those gates. Run genuine inference and task-specific held-out evaluation before marking the backend usable for prediction. Record unsupported features and failures; never replace missing outputs with plausible predictions.
6. Compare cache/no-cache, order changes, absent targets and conditional-vs-joint semantics where applicable. Paper speedups are not local end-to-end measurements.

## Maintenance

Revisit the pinned code and paper revision before adopting newer releases. Refresh call-graph links, contracts, blocker status, license evidence and tests together. Rebuild downloadable references and ZIPs, then perform independent source/privacy review. Do not remove a blocker merely because upstream `main` moved.
