# Implementation playbook

## Keep responsibilities separate

```text
input normalizer → rights/evidence checks → question registry
  → provider adapter → contract validator → versioned policy
  → recommendation/audit → separately authorized executor or human review
```

Reuse your project's language and structure. A new service or database is not required.

- Normalize only what the task needs; preserve meaning and minimize personal information.
- Validate evidence excerpts, source location, collection time and access rights. A reachable URL is not proof of its content or author.
- Keep question IDs, versions, primitives and label definitions in a registry.
- Make provider adapters thin and provider-specific. Preserve refusal, unsupported and not-applicable states; never coerce them to a successful score.
- Reject missing/extra answers, nonfinite values, wrong scales and unknown options.
- Return pure policy recommendations. Keep credentials and external writes out of policy code.
- Put authorization, idempotency, rate limits and kill switches in a separate executor.

## Reusable question patterns

**Retrieval:** separate passage relevance, evidence sufficiency and answer faithfulness. A relevant passage may not support the conclusion. A decision model does not retrieve documents that were never supplied. Injection classification is only a signal, never the security boundary.

**Agent traces:** deterministically check tool names, argument schemas, allowlists and ordering where possible. Separate semantic appropriateness, actual completion and claimed completion. Missing hidden context is unassessable, and a log alone does not prove an external write occurred.

**Support routing:** inject rules through state/configuration, not organization names embedded in a library. Unknown/other options do not replace uncertainty checks. Customer notifications, refunds and restrictions require separate authority.

**High-impact review:** organize relevant, authorized evidence and flag missing information for qualified humans. Do not infer incapacity from absent evidence or use protected traits for eligibility decisions.

## Failure handling

| Condition | Default |
|---|---|
| Missing input or rights | No call; hold/review |
| Invalid request/schema | Stop; fix the contract |
| Authorization failure | Stop; do not print credentials |
| Endpoint/model mismatch | Inspect documented contract before retry |
| Documented transient error | Bounded backoff within total request/time/spend budget |
| Successful transport but invalid answer | Contract failure; hold/review |
| Uncertainty or contradiction | Semantic review, distinct from transport failure |
| Duplicate job | Reuse scoped results; never duplicate downstream actions |

Use fixed reason codes in ordinary logs, not raw state, response bodies or headers. Restricted audit records can separate model/version, question/policy version, evidence references, validity, latency, usage, recommendation and final human judgment. Hashing does not remove privacy or retention obligations.

## Evaluation and rollout

1. Record label disagreement and obtain data rights before external processing.
2. Separate calibration and holdout by person/thread/source.
3. Freeze model, parser, questions and thresholds before holdout evaluation.
4. Report class-level precision/recall, confusion, coverage, selective error and review rate.
5. Define probability calibration metrics and include sample counts and uncertainty. Small zero-error samples do not prove zero risk.
6. Evaluate target languages, ambiguous text, missing evidence, long inputs and out-of-scope cases separately.
7. Measure the full pipeline, retries and human-review cost separately from model-only figures.
8. Progress through design, offline verification, approved live evaluation, shadow, approved limited rollout and monitored rollback. No stage implicitly grants the next stage's authority.
