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

## Image and Box snapshot — checked 2026-10-21

This bounded refresh covers the official Images, Box and model-alias documentation only; it does not revalidate every historical report claim or test live inference.

| TypeSafe direct model | Image input | Box localization |
| --- | --- | --- |
| Jev 1.13 (`jev-1.13.0`) | Supported with opt-in | Not supported; requires 1.14 |
| Jev 1.14 (`jev-1.14.0`) | Supported with opt-in | Supported with opt-in |

- Images and Box are **off by default**, **Dreamer-ready**, and **not production-ready**. Send `TypeSafe-Danger-Zone-Images: true` on **every request** that uses them; selecting a model alone does not enable the feature.
- Images use `assets` with references in `state`, `instructions` or `criteria`; supported formats are PNG and JPEG. This does not add native PDF, audio or video support.
- Box requires Jev 1.14 and has **no criteria**. Its `top`, `bottom`, `left`, `right` edges are normalized to `0..1`.
- Box always returns a box, even for an absent target: there is **no not-found** result. Pair an existence Noul in the **same request** and ignore the box when presence probability is low. The official Box guide gives **no recommended confidence threshold**; do not invent one or substitute Box confidence for presence.
- Do not assume a nullable Box confidence contract from an older OpenAPI snapshot. Any future live parser must verify missing/nullable fields against its pinned current contract, separately from these semantic notes.
- The live Models page checked on this date maps `jev-latest → jev-1.13.0` and `jev-preview → jev-1.14.0`. An extracted-text cache showing both at 1.13 is stale; aliases can move.

The bundled `decision_kit.py` remains **text-only and offline**. It rejects `assets` and `box`; documenting provider features does not enable them or authorize paid calls.

## Version refresh checklist

1. Re-read the official [Models](https://docs.typesafe.ai/models), [Images](https://docs.typesafe.ai/images) and [Box](https://docs.typesafe.ai/go/box) pages. Record the check date and limited scope; resolve stale extractor/browser disagreements instead of copying cached aliases.
2. Pin the exact requested model and validate the actual `response.model` when separately authorized live evaluation occurs. Record endpoint, parser/schema versions and feature headers, including the per-request image opt-in. Documentation lookup is not inference verification.
3. Update this reference, report version tables and source records together. Preserve default-off and experimental warnings, Box existence gating and the offline tool's narrower boundary.
4. Run offline regression tests, including unsupported-media rejection. Rebuild the site, PDF and ZIP downloads; verify source/reference parity, PDF page count and layout, and absence of private data before independent QA and publication.

## Primary references

- [Models](https://docs.typesafe.ai/models)
- [Images](https://docs.typesafe.ai/images)
- [Box](https://docs.typesafe.ai/go/box)

- [System One API](https://docs.typesafe.ai/api/system-one)
- [Noul](https://docs.typesafe.ai/primitives/noul)
- [Choice](https://docs.typesafe.ai/primitives/choice)
- [Score](https://docs.typesafe.ai/primitives/score)
- [Confidence](https://docs.typesafe.ai/confidence)
- [Error handling](https://docs.typesafe.ai/api/errors)
- [Legal documents](https://docs.typesafe.ai/legal)

Links provide attribution and a verification starting point, not affiliation or bundled third-party code. They are not consulted during offline execution.
