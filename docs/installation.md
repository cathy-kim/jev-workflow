# Installation and portability

The public edition is version **1.2.0**. The marketplace is `jev-workflow`, the plugin is `jev`, and the skill is `jev-decisions`. Installation supplies instructions, offline tools and an opt-in live client: no hooks, automatic paid calls, automatic MCP server start or credential discovery. Paid calls happen only with `--live` or an operator-enabled MCP live mode. This document describes user-initiated installation; the included tests do not modify installed settings.

## Runtime adapters and MCP

One canonical skill folder serves every runtime; each runtime discovers it through its own documented mechanism. The bundled installer copies that folder into a directory you name and prints, but never runs, the runtime's MCP registration command:

```bash
python3 plugins/jev/skills/jev-decisions/scripts/jev_cli.py install --runtime codex  --target <repo>/.agents/skills --dry-run
python3 plugins/jev/skills/jev-decisions/scripts/jev_cli.py install --runtime claude --target <project>/.claude/skills
python3 plugins/jev/skills/jev-decisions/scripts/jev_cli.py install --runtime hermes --target <project>/.hermes/skills
python3 plugins/jev/skills/jev-decisions/scripts/jev_cli.py uninstall --target <project>/.hermes/skills
```

| Runtime | Discovery | Invocation | MCP registration (manual) |
|---|---|---|---|
| Claude Code | plugin marketplace, `--plugin-dir`, or `.claude/skills` | `/jev:jev-decisions` / `/jev-decisions` | `claude mcp add --scope project jev-workflow -- python3 <skill>/scripts/jev_cli.py mcp-serve` |
| Codex | `.agents/skills` (repo or `~`) | `$jev-decisions` | `codex mcp add jev-workflow -- python3 <skill>/scripts/jev_cli.py mcp-serve` |
| Hermes | `<project>/.hermes/skills` (after `hermes skills trust`) or `$HERMES_HOME/skills/<category>` | `/jev-decisions` | `hermes mcp add jev-workflow --command python3 --args <skill>/scripts/jev_cli.py mcp-serve` |
| Other | load `SKILL.md` by path | runtime-specific | any stdio MCP client |

The installer refuses an existing different copy unless `--backup` is given, refuses symlinked targets and overlap with its own source, writes `.jev-install.json` with file hashes, reinstalls idempotently and restores the backup on `uninstall` only when installed files are unmodified. It does not edit runtime configuration, enable plugins or start servers. The Claude plugin manifest declares no `mcpServers`. The MCP server starts offline (validation and parsing tools only); see the [live client reference](../plugins/jev/skills/jev-decisions/references/live-client.md) for live mode, environment passing and limits.

## Installable command

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
jev-workflow --version
jev-workflow providers
jev-workflow-mcp --help
```

The wheel contains only the `jev_workflow` package (standard library, no dependencies). Run `install`/`uninstall` from a checkout or extracted skill bundle, because they copy the whole skill folder.

## Claude Code marketplace

After the repository is published and reachable, run these commands inside Claude Code:

```text
/plugin marketplace add cathy-kim/jev-workflow
/plugin install jev@jev-workflow
/jev:jev-decisions
```

Use Claude Code's scope selection if you want project-scoped rather than user-wide installation. Start a fresh session if the new skill is not visible. A successful installation is not proof that a live provider integration works.

Try a bounded prompt:

```text
/jev:jev-decisions Design and implement a support-routing contract.
Use synthetic data only. Run the offline tests and report missing adoption approvals.
Do not call any API or search for credentials.
```

## Project-local plugin without persistent installation

From a checkout of this repository, launch Claude Code with a session-local plugin directory:

```bash
claude --plugin-dir ./plugins/jev
```

Then invoke `/jev:jev-decisions`. When working in another project, pass the absolute path to this checkout's `plugins/jev` directory instead. The plugin directory is self-contained. This launch option is not a marketplace installation and does not require copying settings or overwriting an existing command.

You can validate the manifests without installing anything:

```bash
claude plugin validate ./plugins/jev
claude plugin validate ./.claude-plugin/marketplace.json
```

## Runtime-neutral skill

The only canonical skill is:

```text
plugins/jev/skills/jev-decisions/
  SKILL.md
  references/
  templates/
  scripts/
```

Copy that **whole directory**, not only `SKILL.md`, into a project-local skill directory supported by your runtime, or explicitly ask your assistant to load its `SKILL.md` by path. Preserve the relative layout so references, templates, tests and examples remain available. For a Claude Code project-local non-plugin skill, the conventional destination is `.claude/skills/jev-decisions/`; its invocation is `/jev-decisions`, not the plugin's namespaced command. Choose either the plugin or the copied skill to avoid ambiguous duplicates.

For Hermes or any other skill-capable assistant, use that runtime's documented project-local skill registration or direct file-loading mechanism. This package does not require Hermes-specific metadata, a global skill directory, another skill, a plugin manager, or any secret-store integration. Do not assume all runtimes share an installation path or command syntax. An assistant without skill support can use the workflow as a normal document and run the Python scripts manually.

## Runnable offline demo

The starter targets Python 3.10+ and uses only the standard library. No `pip install`, provider key or network access is needed. From the repository root:

```bash
python3 -B examples/offline_demo.py
```

The demo discovers the checkout from its own file path, so an absolute invocation works from another directory too. It creates synthetic scaffolding in a temporary directory and cleans it up. It runs actual subprocesses and verifies their exit codes:

| Case | Expected exit | Expected outcome |
|---|---:|---|
| init | 0 | Offline files created |
| validate | 0 | Contract shape valid |
| shadow | 3 | REVIEW / SHADOW_ONLY |
| synthetic recommendation | 0 | ROUTE_RECOMMENDATION, no action |
| high-impact policy | 2 | HOLD / HIGH_IMPACT |
| malformed response | 2 | HOLD / INVALID_JSON |

The demo itself exits 0 only if these expectations hold. It prints observed subprocess output, not model inference. Every gate outcome is recommendation-only. Synthetic approval/calibration flags and thresholds are branch-testing fixtures, not operational permission or recommended thresholds.

To inspect or create persistent local scaffolding yourself, read the [offline starter](../plugins/jev/skills/jev-decisions/references/offline-starter.md).

## VideoJev, MJev-Spatial and Jeva research workflows

The [full illustrated guide](guide/index.html#p36) includes an eight-page summary and critical analysis: task selection, architecture, observed code paths, paper/implementation gaps, adoption gates and primary sources. The [research companion](research/index.html) is the shorter browser entry; [full references](../plugins/jev/skills/jev-decisions/references/research-models.md) preserve commit-pinned file/function/line evidence. The PDF contains the same research chapter, not merely a link to a separate page.

These research models are independent of TypeSafe and are not automatically installed or enabled by this skill. For example:

```text
/jev:jev-decisions Summarize VideoJev's temporal-grounding contract and validate a synthetic question list. No inference.
/jev:jev-decisions Explain MJev-Spatial's point contract and current runtime blockers.
/jev:jev-decisions Design Jeva evaluation that separates conditional probabilities, joint mass and null.
```

From a full repository checkout, exercise the research tool:

```bash
python3 -B examples/research_demo.py
python3 plugins/jev/skills/jev-decisions/scripts/research_kit.py plan --task spatial-point
```

In a portable skill bundle, resolve `scripts/research_kit.py` from the skill directory and use its `--help`. The repository-level demo is not part of that smaller bundle. Plans and input validation do not read media, download weights or execute a model. All runtime states remain `UNVERIFIED`; spatial additionally retains `BLOCKED_SOURCE_ISSUES`. A `VALID_CONTRACT_ONLY` result never certifies media provenance, accuracy, permission or runtime availability.

## Verify the package

From the repository root:

```bash
python3 -B -m unittest discover -s plugins/jev/skills/jev-decisions/scripts -p 'test_decision_kit.py' -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
claude plugin validate ./plugins/jev
claude plugin validate ./.claude-plugin/marketplace.json
```

The first command runs the 84-test offline contract suite. Package tests additionally check metadata, relative links, prohibited files, a relocated runtime-neutral copy, the real demo exit codes, the three provider contracts with synthetic fixtures, CLI exit codes, a real MCP subprocess handshake and installer rollback in temporary directories. `-B` prevents bytecode caches in the distributed tree. Local tests use temporary directories; set `TMPDIR` to a trusted scratch directory if desired.

No live API compatibility, model accuracy, calibration, current model availability, or production readiness follows from these checks. See [security boundaries](../SECURITY.md) before adapting the starter.
