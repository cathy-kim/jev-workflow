# Jev Workflow

**Typed decisions, tested offline, adopted deliberately.**

A standalone community toolkit for designing Jev decision workflows: a portable skill with Claude Code, Codex and Hermes installation adapters, an opt-in live client and stdio MCP server for **OpenAI Decisions, TypeSafe System One and OpenRouter**, an offline Python starter, reusable templates and an illustrated Korean guide.

- **[Website & downloads](https://cathy-kim.github.io/jev-workflow/)**
- **[Read the guide](https://cathy-kim.github.io/jev-workflow/guide/)** · [PDF](https://cathy-kim.github.io/jev-workflow/downloads/Jev-Workflow-Guide.pdf)
- [Installation details](docs/installation.md) · [Security & scope](SECURITY.md)

Independent project, not affiliated with TypeSafe, Anthropic, OpenAI, OpenRouter or other named providers. This repository does **not** include model weights. Its live API client sends nothing unless you pass `--live`; live authentication, billing and answer quality were not tested by this project.

## Install in Claude Code

Run these in your shell:

```sh
claude plugin marketplace add cathy-kim/jev-workflow
claude plugin install jev@jev-workflow
claude plugin list
```

Then start a fresh Claude Code session and invoke:

```text
/jev:jev-decisions Design a support-routing workflow. Keep it offline.
```

Inside Claude Code, `/plugin marketplace add cathy-kim/jev-workflow` and `/plugin install jev@jev-workflow` provide the corresponding interactive flow. Confirm installation in the plugin panel when prompted.

For another skill-capable agent, use the complete folder at [`plugins/jev/skills/jev-decisions`](plugins/jev/skills/jev-decisions), not just its `SKILL.md`. There are no required private services, local absolute paths or hooks.

## Use it in Codex, Hermes, other agents and MCP clients

The skill folder is the single source of truth; runtimes only differ in where they discover it. The installer copies it into a directory **you name**, prints the runtime's own MCP registration command without running it, and can roll back:

```sh
python3 plugins/jev/skills/jev-decisions/scripts/jev_cli.py install --runtime codex  --target ./.agents/skills --dry-run
python3 plugins/jev/skills/jev-decisions/scripts/jev_cli.py install --runtime hermes --target ./.hermes/skills
python3 plugins/jev/skills/jev-decisions/scripts/jev_cli.py uninstall --target ./.hermes/skills
```

| Runtime | Install | Invoke |
|---|---|---|
| Claude Code | plugin above, or `--runtime claude --target <project>/.claude/skills` | `/jev:jev-decisions` or `/jev-decisions` |
| Codex | `--runtime codex --target <repo>/.agents/skills` | `$jev-decisions` |
| Hermes | `--runtime hermes --target <project>/.hermes/skills` (then `hermes skills trust`) | `/jev-decisions` |
| Any MCP client | register `python3 <skill>/scripts/jev_cli.py mcp-serve` | offline tools; paid `jev_decide` only with operator `--enable-live` |

These are different native mechanisms, not one shared plugin format. See the [live client reference](plugins/jev/skills/jev-decisions/references/live-client.md).

## Call OpenAI Decisions, TypeSafe or OpenRouter (opt-in)

```sh
python3 -m venv .venv && . .venv/bin/activate && python3 -m pip install .   # or run scripts/jev_cli.py directly
jev-workflow providers                       # offline capability matrix
jev-workflow decide --provider openai --request plugins/jev/skills/jev-decisions/scripts/examples/providers/request.synthetic.json --dry-run
jev-workflow decide --provider typesafe --request my-request.json --live    # paid; reads only TYPESAFE_API_KEY
```

- `--provider openai` → `POST /v1/decisions`, default `gpt-6-luna`, `OPENAI_API_KEY`.
- `--provider typesafe` → `POST /v1/systemone`, default pinned `jev-1.14.0`, `TYPESAFE_API_KEY`; experimental images/Box need `--experimental-images`.
- `--provider openrouter` (default) → OpenRouter Decisions with `~typesafe/jev-latest`, `OPENROUTER_API_KEY`; `--openrouter-mode structured --model …` is a general-LLM JSON judge whose probabilities are **uncalibrated**.

Every result records provider, route, requested and reported model, usage, refusals/not-applicable answers and where each value came from. Unsupported features fail before any network call; malformed responses fail closed. There is no automatic provider or model fallback.

## Try it without credentials

Python 3.10+; the core starter uses only the standard library.

```sh
git clone https://github.com/cathy-kim/jev-workflow.git
cd jev-workflow
python3 -B -m unittest discover -s plugins/jev/skills/jev-decisions/scripts -p 'test_decision_kit.py' -v
python3 examples/offline_demo.py
python3 -B -m unittest discover -s tests -v
```

The demo uses **synthetic fixtures** and returns a recommendation only. Shadow-mode `REVIEW` is expected. It does not call a model, inspect credentials, send data, change a production setting or execute a downstream action. Your agent runtime itself can still call its configured model; this toolkit does not make that runtime free or offline.

## What to ask

- **Support routing:** design separate questions for department, evidence sufficiency and urgency; write malformed-response tests.
- **RAG:** distinguish passage relevance, answer sufficiency and source support; preserve access controls.
- **Agent evaluation:** check schemas and tool order deterministically, then add semantic evaluation without treating N/A as success.
- **Adoption:** define a labeled holdout, calibration protocol, cost cap and rollback plan before live inference.

The workflow is **design → typed questions → adapter boundary → offline tests → evaluation → shadow adoption**. The skill gives repeatable steps and templates; the starter validates only a limited normalized text contract. The live client covers three documented provider routes; re-check current official documentation before relying on any of them.

## Full guide: research summary and analysis

The [43-page HTML guide](https://cathy-kim.github.io/jev-workflow/guide/#p36) and [PDF](https://cathy-kim.github.io/jev-workflow/downloads/Jev-Workflow-Guide.pdf) now include an eight-page research chapter, not just external links:

- **VideoJev:** temporal/choice scoring, event-absence limits, Joint/vision reuse versus research prefix caching, evaluation and training differences.
- **MJev-Spatial:** native Q/K and coarse-to-fine spatial judgment, units/coordinate contracts, source/release blockers and checkpoint-provenance limits.
- **Jeva:** immutable option memory, competition versus coverage/null, typed/raw API differences, permutation/cache evaluation and training-reproduction gaps.
- A comparison matrix, three architecture diagrams, safe adoption steps and six primary paper/repository entries connect the analysis to the executable offline tools.

See the [installation and usage explanation](docs/installation.md) and the authored [research chapter source](report/research-chapter.html). Editing that chapter and running `python3 scripts/build_site.py` synchronizes the full HTML guide; `python3 scripts/render_pdf.py` also synchronizes it before rendering the PDF. Rendering needs optional Playwright/Chromium tooling, not a model provider.

## Video, spatial and null-aware research

Read the [research companion](https://cathy-kim.github.io/jev-workflow/research/) and [selection guide](plugins/jev/skills/jev-decisions/references/research-models.md). Full paper-to-code references cover VideoJev, MJev-Spatial and Jeva at pinned public revisions, including implementation gaps and licenses. These are separate research models, not new TypeSafe API IDs.

```sh
python3 plugins/jev/skills/jev-decisions/scripts/research_kit.py plan --task video-grounding
python3 plugins/jev/skills/jev-decisions/scripts/research_kit.py plan --task spatial-point
python3 plugins/jev/skills/jev-decisions/scripts/research_kit.py plan --task text-choice
python3 examples/research_demo.py
```

The planner and input validator are executable offline tools, **not model inference adapters**. No weights or upstream implementation are bundled. Model execution and benchmark reproduction remain unverified; MJev-Spatial has additional source/release blockers. Do not send internal media or data to public demos.

## Repository map

```text
.claude-plugin/marketplace.json   Public plugin catalog
pyproject.toml                  Installs jev-workflow / jev-workflow-mcp from the skill's scripts/
plugins/jev/                     Claude Code plugin
  skills/jev-decisions/          Canonical portable skill, offline starter and live client
    scripts/jev_workflow/        Provider client, CLI, MCP server and installer (stdlib only)
examples/                       Runnable synthetic example
tests/                          Packaging and portability checks
report/guide.html               Sanitized public report source
report/sources.json             Public source links and reading notes
site/index.html                 Website source
scripts/                        Static site and PDF generators
docs/                           GitHub Pages output and installation guide
```

The public report is a dated technical snapshot, **not a fresh benchmark**. Model IDs, price examples, limits and experimental media features must be rechecked before use. Third-party names and linked content retain their respective owners' rights; no third-party implementation or model is bundled.

## Build the website and report

```sh
python3 scripts/build_site.py
```

This builds the static site plus deterministic plugin/skill ZIPs. GitHub Pages serves `main:/docs`; no custom domain or backend is needed. The downloadable PDF is committed separately and regenerated with optional browser tooling:

```sh
python3 -m venv .venv
# Activate the environment for your operating system.
python3 -m pip install -r requirements-render.txt
python3 -m playwright install chromium
python3 scripts/render_pdf.py
```

An existing Chrome/Chromium can be selected with `--browser /path/to/chromium`. Rendering needs Korean fonts available on the host. PDF generation is a build operation, not a plugin install step; browser downloads are optional and explicit. PDF bytes may differ by browser/fonts, while report source is versioned.

## Contributing

Keep changes narrowly scoped; add offline regression tests and describe verification. Never include credentials, customer traces, personal conversations, internal deployment data or private repository exports. Synthetic examples must remain clearly labeled. Do not turn policy recommendations into automatic actions or silently add network access to the offline starter.

## 한국어

Jev 판단을 자신의 워크플로에 도입하기 위한 공개 스킬·플러그인과 가이드입니다. Claude Code·Codex·Hermes·MCP 클라이언트에서 쓸 수 있고, OpenAI Decisions·TypeSafe·OpenRouter 중 하나를 고르는 클라이언트가 들어 있습니다. 기본은 오프라인이며, `--live`는 `--provider`(또는 `JEV_PROVIDER`)를 명시해야만 동작하고 선택한 provider 키 하나만 읽어 유료 호출합니다. 실제 데이터 전송·배포는 별도 승인이 필요합니다. [한국어 가이드](https://cathy-kim.github.io/jev-workflow/guide/)에서 전체 개념과 도입 절차를 읽을 수 있습니다.

## License

MIT for this repository's authored code and documentation. See [LICENSE](LICENSE). Referenced third-party services, documentation and models are not relicensed by this project.
