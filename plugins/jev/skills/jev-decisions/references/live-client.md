# Live client: OpenAI Decisions, TypeSafe System One and OpenRouter

Version 1.2.0 adds `jev_workflow`, a standard-library Python 3.10+ client, CLI and stdio MCP server. It lives in this skill's `scripts/` folder, so the skill bundle runs it directly; the repository's `pyproject.toml` installs the same package with the `jev-workflow` and `jev-workflow-mcp` commands.

**Live calls are opt-in.** Validation, dry runs, capability listing, `doctor`, saved-response parsing, the installer and the default MCP server never contact a network and never read a credential. Only `decide --live`, `ask --live` or an MCP server that its operator started with `--enable-live` sends a paid request, and only to the one provider that was selected. There is no fallback to another provider, route or model.

What was verified: request/response contracts against the official sources listed below (read 2026-10-24) and synthetic offline fixtures. What was **not** verified: live authentication, account availability, billing, latency or answer quality for any provider.

## Choose a provider

| | `openai` | `typesafe` | `openrouter` (default) |
|---|---|---|---|
| Route | `openai.decisions` | `typesafe.systemone` | `openrouter.decisions` (default) or `openrouter.structured` |
| Endpoint (fixed) | `https://api.openai.com/v1/decisions` | `https://api.typesafe.ai/v1/systemone` | `https://openrouter.ai/api/alpha/decisions` / `https://openrouter.ai/api/v1/chat/completions` |
| Credential (env only) | `OPENAI_API_KEY` | `TYPESAFE_API_KEY` | `OPENROUTER_API_KEY` |
| Default model (pinned) | `gpt-6-luna` | `jev-1.14.0` | `~typesafe/jev-latest` (decisions); structured requires `--model` |
| Noul | `predicate` probability | `noul` probability | decisions: `noul`; structured: generated probability |
| Noul `criteria` | not supported (put guidance in instructions) | supported | supported |
| Choice values | string **or boolean** (typed) | string only | string only |
| Score | expected level index 0..n-1 | expected level index 0..n-1 | decisions: provider index; structured: client-derived from generated level probabilities |
| Per-question refusal | yes (`status: refused`) | not in contract | decisions: not in contract; structured: `refused` / `not_applicable` |
| Images / Box | provider supports images; **not implemented** in this client | implemented, experimental opt-in; Box only on pinned `jev-1.14.0` | not implemented in this client |
| Value origin label | `provider_decision_model` | `provider_decision_model` | `provider_decision_model_via_openrouter` / `llm_generated_json_uncalibrated` |

`jev-workflow providers` prints the full machine-readable matrix, including limits (OpenAI 1–400 questions, 2–255 choices, 2–10 levels; `input_json` 256 KiB / 32 levels / 10,000 values).

### Semantics that are easy to get wrong

- **Score is an expected 0-based level index, not 0–1.** The result keeps the raw value, the per-level distribution and `derived.normalized_0_1`. Current OpenAI and TypeSafe documentation both describe a probability-weighted mean of level indices; values from different providers or models are still **not interchangeable** and need separately tuned thresholds. A signed score scale was not found in the current TypeSafe OpenAPI.
- **Confidence is not probability and not accuracy.** `null` means "not provided" (for example OpenRouter structured, optional OpenRouter Decisions fields, or a nullable Box confidence). It is never converted to 0.
- **Refused and not-applicable are not false, zero or pass.** `summary` counts `answered`, `refused` and `not_applicable` separately.
- **OpenRouter structured mode is an LLM judge.** A general model fills a strict JSON schema; its probabilities are generated text, not calibrated decision-model outputs. OpenRouter Decisions routes to a dedicated decision model (Jev by default); any calibration claim belongs to that upstream provider and is not verified by this client.
- **Box always returns a box.** Pair it with a presence noul in the same request; there is no not-found answer and no documented threshold.

### Fail-closed parsing

Responses must contain exactly one answer per requested id (OpenAI also in request order), the documented type and fields, finite numbers inside their ranges (booleans are not numbers), complete typed option/level distributions summing to 1 within a small rounding tolerance, non-negative integer usage counts, and a reported model that matches the request (exact for pinned TypeSafe IDs, dated snapshot suffix for OpenAI/OpenRouter slugs, recorded resolution for aliases). OpenRouter Decisions requests send `provider.allow_fallbacks: false`; a different upstream provider in the response is rejected. Anything else raises `malformed_response` (exit 5) and no partial result is returned.

## CLI

From a checkout or extracted skill (`python3 scripts/jev_cli.py …` inside the skill folder), or after `python3 -m pip install .` in a virtual environment (`jev-workflow …`):

```bash
jev-workflow providers                                   # offline matrix
jev-workflow capabilities --provider typesafe --model jev-1.13.0
jev-workflow doctor                                      # no network, no credential inspection
jev-workflow validate --provider openai --request scripts/examples/providers/request.synthetic.json
jev-workflow decide --provider typesafe --request - --dry-run < request.json
jev-workflow parse --provider openai --request scripts/examples/providers/request.synthetic.json \
  --response scripts/examples/providers/openai.response.synthetic.json
jev-workflow ask --provider openrouter --dry-run --state "Synthetic: charged twice" \
  --noul "Is this about billing?" --choice "Team?" --option billing --option technical
```

A paid call is the same command with `--live` instead of `--dry-run`, after you have approval for the data, provider, model, request count and budget. Example syntax only:

```bash
export OPENAI_API_KEY=...   # set by you in your shell; never passed as an argument
jev-workflow decide --provider openai --request request.json --live
```

Configuration precedence: `--provider` flag, then `JEV_PROVIDER`, then `openrouter`. Models come from `--model` or the provider's pinned default; there is no model environment variable. `JEV_BASE_URL`, `JEV_MODEL` and `HTTP(S)_PROXY`/`ALL_PROXY` are ignored. Unlisted models need `--allow-unlisted-model`.

Request format (`jev.request.v1`): `state` (string, object or array), ordered `questions` with `id`, `type` (`noul`/`predicate`, `choice`, `score`, `box`), `instructions`, and `criteria` (`{"true","false"}`), `options` (`[{"value","description"}]`) or `levels` (`[{"label","description"}]`). Images are `--image REF=PATH` (PNG/JPEG, explicit path, REF must appear in `state`) plus `--experimental-images`. Remote image URLs are rejected; nothing is fetched locally.

Exit codes: `0` success, `2` invalid input, `3` credential missing/invalid/rejected, `4` provider HTTP or transport failure, `5` malformed response, `6` unsupported capability (before any transport). stdout always carries one JSON document; stderr carries a one-line diagnostic.

Transport: fixed HTTPS endpoints, no redirects (credentials never follow), no environment proxies, 8 MiB response cap, per-attempt timeout (default 30 s), at most 3 attempts within a 90 s deadline, retries only for documented transient statuses (OpenAI 429/5xx, TypeSafe 429/529/5xx, OpenRouter 429/502/503/524/529) and connection failures; `Retry-After` honoured up to 30 s. Protocol corruption (for example `IncompleteRead`) is not retried. Error bodies and exception text are never printed; a credential found in a request or echoed in a response stops the call.

## MCP server (any stdio MCP client)

`jev-workflow mcp-serve` (or `python3 scripts/jev_cli.py mcp-serve`) speaks newline-delimited JSON-RPC 2.0 (protocol versions 2025-11-25, 2025-06-18, 2025-03-26, 2024-11-05). Default tools are offline: `jev_list_providers`, `jev_capabilities`, `jev_validate_request`, `jev_parse_response`. They accept no file paths and run no shell or arbitrary network access; input lines are limited to 1 MiB and tool arguments to 512 KiB.

The paid `jev_decide` tool is registered only when the operator starts the server with all of `--enable-live --live-provider P --max-live-requests N` (1–1000). Tool arguments cannot change the provider, model or budget, unsupported payloads fail before transport, and output is key-redacted. `readOnlyHint`/`openWorldHint` annotations are client hints, not billing consent. Many MCP clients filter environment variables, so a live server needs its provider key passed explicitly through that client's env setting.

Registration is a separate, manual step per runtime (the installer prints these; it never runs them):

```bash
claude mcp add --scope project jev-workflow -- python3 <SKILL>/scripts/jev_cli.py mcp-serve
codex mcp add jev-workflow -- python3 <SKILL>/scripts/jev_cli.py mcp-serve
hermes mcp add jev-workflow --command python3 --args <SKILL>/scripts/jev_cli.py mcp-serve
```

## Runtime adapters

One canonical skill (this folder) is the behavioural source of truth. Runtimes differ in how they discover it; they are not the same plugin format:

| Runtime | Native form | How to install | Invocation |
|---|---|---|---|
| Claude Code | plugin (`plugins/jev`, marketplace `jev-workflow`) or project skill | `claude plugin install jev@jev-workflow`, or `jev-workflow install --runtime claude --target <project>/.claude/skills` | `/jev:jev-decisions` (plugin) or `/jev-decisions` (skill) |
| Codex | skill folder in `.agents/skills` | `jev-workflow install --runtime codex --target <repo>/.agents/skills` | `$jev-decisions` |
| Hermes | skill folder in `<project>/.hermes/skills` or `$HERMES_HOME/skills/<category>` | `jev-workflow install --runtime hermes --target …` (project skills need `hermes skills trust`) | `/jev-decisions` |
| Other agents | `SKILL.md` + neighbouring folders | `--runtime generic` or copy the folder | load `SKILL.md` by path |
| MCP clients | stdio server | manual registration above | tool calls |

The installer requires an explicit `--target`, supports `--dry-run`, refuses an existing different copy unless `--backup` moves it aside, refuses symlinked targets and overlap with the source, writes a hash manifest, reinstalls idempotently and `uninstall` restores the backup only when installed files are unmodified. It never edits runtime configuration, never enables a plugin and never starts the MCP server. The Claude plugin deliberately declares no `mcpServers`, so enabling it cannot auto-start a server.

## Sources read on 2026-10-24

- OpenAI: [Decisions guide](https://developers.openai.com/api/docs/guides/decisions.md), [create decision reference](https://developers.openai.com/api/reference/typescript/resources/decisions/methods/create/index.md). The reference's example response uses placeholder negative token counts; they are not valid usage values and this client rejects negative usage.
- TypeSafe: [llms.txt](https://docs.typesafe.ai/llms.txt), [OpenAPI](https://api.typesafe.ai/openapi.json), [System One](https://docs.typesafe.ai/api/system-one), [Models](https://docs.typesafe.ai/models), [Images](https://docs.typesafe.ai/images), [Box](https://docs.typesafe.ai/primitives/box), [Errors](https://docs.typesafe.ai/api/errors). Source-specific differences: the OpenAPI allows 1-option choices and 1-level scores while the guides recommend at least two (this client requires 2); the Models table lists input as text while the Images page documents experimental image input; the 2026-10-24 Models page maps both `jev-latest` and `jev-preview` to `jev-1.14.0`; the current OpenAPI marks Box confidence nullable.
- OpenRouter: [Structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs.md), [Jev on OpenRouter](https://openrouter.ai/docs/guides/community/jev.md), [Decisions API reference](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request.md), [provider routing](https://openrouter.ai/docs/guides/routing/provider-selection.md). Structured-output enforcement varies by endpoint, so the client sends `require_parameters: true` and `allow_fallbacks: false`.
- Runtimes: [Codex skills](https://developers.openai.com/codex/skills/), [Codex MCP](https://developers.openai.com/codex/mcp), [Claude Code plugins reference](https://code.claude.com/docs/en/plugins-reference), [Hermes docs index](https://hermes-agent.nousresearch.com/docs/llms.txt), [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) and [tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

Model IDs, aliases, limits and prices change. Re-read these sources and re-run the offline tests before relying on a route; documentation review is not live verification.
