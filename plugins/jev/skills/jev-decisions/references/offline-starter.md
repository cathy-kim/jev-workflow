# Offline contract starter

**SYNTHETIC/OFFLINE only. No inference, network, credentials, ticket assignment, refunds, notifications or deployment.**

This standard-library Python exercise validates a restricted TypeSafe-style text contract and recommends a fictional support-ticket department. It is not a production SDK, a complete API implementation, an accuracy benchmark or a calibrated policy. Python 3.10+ is the intended minimum; test on your actual interpreter and OS before adoption.

## Run locally

From this skill's directory, choose a new trusted output directory:

```bash
python3 -B scripts/decision_kit.py init --out demo-new
python3 -B scripts/decision_kit.py validate --request demo-new/request.json --response demo-new/response.synthetic.json
python3 -B scripts/decision_kit.py gate --request demo-new/request.json --response demo-new/response.synthetic.json --policy demo-new/policy.json
python3 -B -m unittest discover -s scripts -p 'test_decision_kit.py' -v
```

The third command intentionally exits **3**, returning `REVIEW` / `SHADOW_ONLY`. Do not put it into a success-only shell chain without handling that expected exit. A gate exit of 0 means a recommendation, never permission to execute it.

| Exit | Meaning |
|---|---|
| 0 | init completed, validate accepted structure, or gate returned ROUTE_RECOMMENDATION |
| 2 | input/policy error or HOLD |
| 3 | REVIEW: shadow, uncertainty or unsupported department |

Every gate result includes `recommendation_only: true` and `action_executed: false`. Errors use fixed reason codes rather than raw input, arbitrary labels, paths or exception tracebacks.

`init` writes only the requested output directory and needed parents. It preserves unrelated files, rejects existing planned targets before writing, and uses exclusive creation. It rejects static symlink ancestors but is not a transaction or a concurrent-path-mutation sandbox. Use one process and a trusted local directory; failures mid-write can leave some newly created files.

## Generated files

- `design.md`: provider/model, risk, state/rights, evaluation and rollout/rollback questions.
- `request.json`: synthetic text state and Noul/Choice/Score questions. These questions are the validation rubric's source of truth.
- `rubric.json`: design copy for review only. The CLI does **not** consume or synchronize it; update request questions explicitly when changing it.
- `policy.json`: shadow mode, false approval/calibration flags, null references and thresholds. It cannot produce a route recommendation as written.
- `response.synthetic.json`: handwritten probabilities and token counts, not an actual API response. Zero tokens do not represent a measured cost.

`jev-1.14.0` demonstrates an exact model-identifier format. It is not proof of provider availability or approval.

## Restricted request contract

Root fields are exactly `model`, `state`, `questions`.

- Model, text state, question IDs and instructions must be nonempty strings.
- There must be 1–100 questions. Question fields are `type`, `instructions`, optional `criteria` only.
- Noul criteria may be absent/null, or exactly a `true`/`false` map of nonempty descriptions.
- Choice criteria contain 2–255 option IDs mapped to nonempty descriptions.
- Score criteria contain 2–10 nonempty ordered level descriptions.
- Structured state, media/assets, Box, streaming, gateway envelopes and extra API fields are rejected. These are starter limits, not claims about the provider's full capabilities.

## Restricted response contract

Root fields are exactly `model`, `answers`, `usage`.

- Reported model must be a nonempty string. `validate` does not resolve aliases or enforce equality; `gate` enforces exact model equality.
- Answer ID sets must exactly match questions and answer types must match.
- Noul requires a finite non-boolean probability in `[0,1]`; confidence is optional and checked if present.
- Choice requires choice, confidence and probabilities. Distribution keys must match all criteria options; the choice must be a maximum-probability option. Ties are structurally valid but fail the gate's positive-margin requirement.
- Score requires score, confidence and probabilities indexed by exact zero-based string keys. Score must equal the distribution's expected level and fall within `[0, levels-1]`. Optional legend must exactly match the request rubric.
- Probabilities and confidence must be finite non-boolean numbers in `[0,1]`. Distribution sum and Score consistency use absolute tolerance `1e-6`. No clamping, automatic normalization or key repair occurs.
- Usage contains exactly nonnegative integer `input_tokens` and `output_tokens`, excluding booleans.
- Unknown fields are rejected. Confidence calculation and calibration are not verified.

JSON rejects duplicate keys at any depth, nonfinite constants, overflow floats and invalid syntax. Each input is limited to 1 MiB and read as UTF-8 from a caller-selected regular file. Excessive nesting fails with a safe error.

## Fictional ticket gate

This is not a general policy engine. The `detail` Score is validated but does not affect routing.

1. Validate request/response and require `evidence_sufficient: noul` plus `department: choice`.
2. Require exact purpose `internal_ticket_routing`, real boolean flags and the expected policy field set.
3. `high_impact: true` always returns HOLD. Classification is the human designer's responsibility.
4. Require pinned model format `jev-N.N.N` and literal equality with both request and response model identifiers. No alias resolution or whitespace repair.
5. Omitted mode defaults to shadow. Shadow returns REVIEW without a route, but malformed data, invalid policy or model drift still HOLD.
6. Recommend mode requires true approval/calibration flags, nonempty references and set thresholds. These are **local declarations, not authenticated approval or calibration evidence**.
7. Thresholds are finite non-boolean `[0,1]` numbers. Evidence minimum must exceed 0.5, department probability minimum must be at least 0.5, and confidence/margin minima must be positive. These code constraints are not recommended production settings.
8. Criteria must include unknown and other. Only billing, shipping and returns can be recommended; other selections REVIEW.
9. Evidence probability, selected probability, confidence and the top-two probability margin must all meet their thresholds. Otherwise REVIEW. Do not use distribution tolerance to bypass policy thresholds.

The [synthetic recommendation policy](../scripts/examples/policy.synthetic-recommend.json) and [high-impact fixture](../scripts/examples/policy.synthetic-high-impact.json) exist only to test branches. Do not reuse their values as real approvals, calibrated thresholds or accuracy evidence.

## Trust limits and verification

The starter does not authenticate response origin/freshness, input-state binding, approval identity, calibration reports, data rights, task impact or question semantics. Production audit storage, network adapters, credential management, retries and actual ticket execution are out of scope.

The [84-test suite](../scripts/test_decision_kit.py) checks invalid/boundary contracts, CLI codes, file preservation, drift, non-leaking errors and hostile JSON types. It also checks an import allowlist and exercises a gate under a runtime network/external-process audit guard. Passing tests are evidence for tested paths, not a universal sandbox or proof of real API quality.

Reference contracts: [System One](https://docs.typesafe.ai/api/system-one), [Choice](https://docs.typesafe.ai/primitives/choice), [Score](https://docs.typesafe.ai/primitives/score). Links are not fetched during execution.
