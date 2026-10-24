# Security and trust boundaries

## Scope

Version 1.2.0 is an offline-first workflow, a deliberately restricted contract starter and an opt-in multi-provider client (`jev_workflow`). It contains no hooks, telemetry, secret discovery or automatic installation. Everything uses only the Python standard library; tests and demos run local subprocesses and synthetic transports.

## Live client boundaries

- Nothing is sent unless `--live` is passed, or an MCP server operator starts it with `--enable-live --live-provider P --max-live-requests N`. Validation, dry runs, `doctor`, `parse`, the installer and the default MCP server never open a network connection or read a credential.
- Only the selected provider's variable is read (`OPENAI_API_KEY`, `TYPESAFE_API_KEY`, `OPENROUTER_API_KEY`), at call time. No dotenv files, keychains, password managers or command-line keys. Keys are redacted from output; a request containing the key, or a response echoing it, is rejected.
- Endpoints are fixed HTTPS origins. Redirects are not followed, environment proxies are ignored, responses are size-bounded, retries are limited to documented transient statuses within a deadline, and error bodies/exception text are never printed.
- Remote image URLs are rejected and nothing is fetched locally; images are explicit local PNG/JPEG files and are experimental (TypeSafe only).
- MCP tool arguments cannot enable live mode, switch provider/model or raise the budget. Tool annotations are not billing consent.
- The installer needs an explicit target, refuses collisions and symlinks unless told to back up, and never edits Claude Code, Codex, Hermes or MCP client configuration.
- A sent request transfers your state to that provider under its own terms. Live authentication, account availability, billing and answer quality were not tested by this project.

The authored code and documentation are MIT-licensed; linked third-party services, documents, trademarks and implementations retain their own terms. This community project is not affiliated with or endorsed by TypeSafe, Jev's provider, Anthropic, OpenAI, OpenRouter, or any linked project. No third-party SDK or tutorial implementation is vendored.

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
