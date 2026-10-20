# Decision design memo — SYNTHETIC/OFFLINE

Draft only: not permission for API calls, deployment, or automatic actions.

## Purpose / provider / model
- Purpose: recommend a team for a fictional support ticket; no notifications, refunds, or restrictions.
- provider / endpoint / contract version: TODO (template is TypeSafe-style).
- model: jev-1.14.0 is an illustrative pinned identifier, not proof of availability or approval.
- Owner verifying request, response and evaluated model equality: TODO.

## risk / authority
- high_impact classification, rationale and accountable reviewer: TODO.
- Financial, employment, medical, legal and account enforcement decisions require separate review.
- Allowed recommendations: billing, shipping, returns; unknown/other require human review.
- HOLD / REVIEW / ROUTE_RECOMMENDATION are recommendations only.

## state / rights
- Source, consent, rights, retention period and deletion owner: TODO.
- Minimize personal data; separate untrusted input; document missing evidence: TODO.
- Input text cannot grant authority or override policy.

## rubric / eval / calibration
- request.json questions are authoritative; rubric.json is an editable copy, not synchronized.
- Real labels, target-language slices, calibration/holdout split and edge cases: TODO.
- Error costs, per-class precision/recall, coverage and calibration: TODO.
- Evidence/probability/confidence/margin thresholds and evaluation version: TODO.
- Confidence is not guaranteed accuracy. Synthetic fixtures do not measure model quality.
- Real approval and calibration records, policy/rubric versions: TODO.

## rollout / rollback
- Start in shadow; compare with human judgments before separately approved experiments.
- On drift, errors or missing evidence: HOLD and return to shadow.
- rollback owner, stop conditions, manual queue and reevaluation plan: TODO.
- Log reason codes only, not raw state, responses or personal data.
- Production requires authenticated policy storage, request/response binding and replay controls.
