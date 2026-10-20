# Provider and evaluation boundaries

The workflow is portable; the included parser is intentionally not a universal adapter. No external provider, evaluation SDK or model is installed by this package.

## Keep adapters distinct

For every provider, record endpoint, exact model ID, headers, request/response fixtures, parser version, limits and data handling. Do not assume a gateway response envelope matches a direct provider, that an OpenAI-compatible surface implies identical semantics, or that two similarly named models are interchangeable.

- Preserve provider refusal as a distinct outcome rather than a false answer.
- Track applicable-answer count and coverage separately from aggregate scores. A metric that yields a favorable default when all answers are inapplicable must not pass readiness.
- Keep transport success, contract validity, semantic correctness, calibration and action authorization separate.
- A local open-model readout is not evidence of hosted-provider behavior. Local inference still has compute costs; remote backends transmit data.
- Evaluation/observability integrations may create datasets or experiments even when the underlying inference is a demo. Require separate approval for those writes.
- Synthetic fixture results measure plumbing and branches only. Saved benchmark claims are not locally reproduced measurements.

## Comparative evaluation record

Use the same authorized held-out examples and label policy when comparing providers. Record model/parser/question versions, refusal and missing rates, coverage, selective error, class-level confusion, calibration definitions, sample counts and uncertainty. Compare full-pipeline latency and costs including retries and review, not just advertised token prices.

Treat public tutorials as design references, not operational authority. Verify dependencies, licenses, contracts, data transmission and secret handling before adopting any third-party implementation. This distribution contains authored workflow documentation and an offline starter, not vendored SDK or tutorial implementations.

## Reference starting points

- [TypeSafe documentation](https://docs.typesafe.ai/)
- [OpenRouter documentation](https://openrouter.ai/docs)
- [OpenAI platform documentation](https://platform.openai.com/docs)
- [DeepEval documentation](https://deepeval.com/docs)
- [Opik documentation](https://www.comet.com/docs/opik/)

These links are not runtime dependencies or claims of affiliation. Re-check the relevant current documentation before any separately authorized live integration.
