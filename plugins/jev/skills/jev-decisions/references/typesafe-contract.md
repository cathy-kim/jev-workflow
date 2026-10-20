# TypeSafe-style contract notes

These are integration design notes, not a current API guarantee. The bundled tool does not fetch documentation, contact a provider, or ship an SDK. Before authorized live work, inspect the provider's current official contract and pin the endpoint, exact model, parser and schema versions.

## Primitive semantics

- **Noul:** a probability for a positively stated event. Keep missing/refused evidence separate from a low probability. Do not require a confidence field unless the provider contract does.
- **Choice:** stable option IDs with explicit descriptions. Validate returned IDs and distribution keys against the exact request options; preserve uncertainty and fallback choices.
- **Score:** ordered, self-contained level descriptions. An expected level is not a probability. Retain the distribution and original scale when deriving normalized/composite values.

Confidence is provider-specific and is not an accuracy guarantee or execution permission. Do not transplant confidence formulas or thresholds between providers. Contract validation does not prove calibration.

## Boundaries to verify for a live adapter

- Shared state and independent questions; dependent questions need separate stages.
- Exact request/response shapes, feature headers, SDK defaults and raw HTTP differences.
- Limits, timeout/retry behavior and error envelopes; avoid nested retry loops.
- Missing versus nullable fields, refusal and unknown answer types.
- Media support per provider/endpoint/model. Text-only success does not validate images, audio or video.
- Logging, processing location, retention, subprocessors and applicable data agreement. No-training claims do not imply no storage or zero retention.

The [offline starter](offline-starter.md) intentionally supports less than a full API: only text state and Noul/Choice/Score with strict field sets. Unsupported features fail closed rather than being silently accepted.

## Primary references

- [System One API](https://docs.typesafe.ai/api/system-one)
- [Noul](https://docs.typesafe.ai/primitives/noul)
- [Choice](https://docs.typesafe.ai/primitives/choice)
- [Score](https://docs.typesafe.ai/primitives/score)
- [Confidence](https://docs.typesafe.ai/confidence)
- [Error handling](https://docs.typesafe.ai/api/errors)
- [Legal documents](https://docs.typesafe.ai/legal)

Links provide attribution and a verification starting point, not affiliation or bundled third-party code. They are not consulted during offline execution.
