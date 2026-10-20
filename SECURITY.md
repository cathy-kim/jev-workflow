# Security and trust boundaries

## Scope

Version 1.0.0 is an offline-first workflow and a deliberately restricted contract starter. It contains no provider client, hooks, MCP configuration, telemetry, secret discovery or automatic installer. The Python starter uses only the standard library; tests and the demo run local Python subprocesses.

The authored code and documentation are MIT-licensed; linked third-party services, documents, trademarks and implementations retain their own terms. This community project is not affiliated with or endorsed by TypeSafe, Jev's provider, Anthropic, OpenAI, or any linked project. No third-party SDK or tutorial implementation is vendored.

## What the starter does not guarantee

- A structurally valid response is not proof of accuracy, calibration, origin or freshness.
- Matching model and question identifiers does not cryptographically bind a response to its state.
- Approval/calibration flags and references are untrusted local declarations, not authenticated authorization.
- `high_impact: false` does not prove that a task is low-risk; a human must classify the use case.
- `ROUTE_RECOMMENDATION` and exit code 0 never execute or authorize an action.
- Synthetic fixtures and zero token counts are not actual inference, measured costs or real customer data.
- `init` rejects existing targets and static symlink ancestors, but is not a transactional or race-proof filesystem sandbox. Use a trusted local directory without concurrent mutation. A mid-write failure can leave some new files.
- JSON input files are explicitly selected by the caller. Do not give an untrusted caller arbitrary local-file selection. The starter bounds size and sanitizes ordinary errors but is not a general untrusted-file sandbox.

## Safe integration

Keep the default shadow mode. Obtain explicit permission before external data transfer, live inference, observability writes, deployment or automation. Define rights, minimization, retention, budgets, qualified review, rollback and kill switches. Never connect model output directly to shell execution, financial actions or access control.

Do not paste secrets or sensitive input into issues. Prefer synthetic reproductions. If GitHub private vulnerability reporting is enabled, use the repository's Security tab. Otherwise open a minimal issue requesting a private contact channel without disclosing exploit details or private data. Private reporting availability and response times are not guaranteed by this package.
