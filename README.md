# Jev Workflow

**Typed decisions, tested offline, adopted deliberately.**

A standalone community toolkit for designing Jev decision workflows: an installable Claude Code plugin, a portable skill, an offline Python starter, reusable templates and an illustrated Korean guide.

- **[Website & downloads](https://cathy-kim.github.io/jev-workflow/)**
- **[Read the guide](https://cathy-kim.github.io/jev-workflow/guide/)** · [PDF](https://cathy-kim.github.io/jev-workflow/downloads/Jev-Workflow-Guide.pdf)
- [Installation details](docs/installation.md) · [Security & scope](SECURITY.md)

Independent project, not affiliated with TypeSafe, Anthropic, OpenAI or other named providers. This repository does **not** include model weights or a live API client.

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

For another skill-capable agent, use the complete folder at [`plugins/jev/skills/jev-decisions`](plugins/jev/skills/jev-decisions), not just its `SKILL.md`. Read your runtime's documented skill installation procedure. There are no required private services, local absolute paths, hooks or MCP servers.

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

The workflow is **design → typed questions → adapter boundary → offline tests → evaluation → shadow adoption**. The skill gives repeatable steps and templates; the starter validates only a limited normalized text contract. Implement a provider-specific live adapter separately against current official documentation.

## Repository map

```text
.claude-plugin/marketplace.json   Public plugin catalog
plugins/jev/                     Claude Code plugin
  skills/jev-decisions/          Canonical portable skill and offline starter
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

Jev 판단을 자신의 워크플로에 도입하기 위한 공개 스킬·플러그인과 가이드입니다. 설치 후 요청 범위와 근거를 먼저 정의하고, 합성 예제·오프라인 테스트로 실패 경로부터 검증합니다. 실제 API 연동·데이터 전송·배포는 별도 구현과 승인이 필요합니다. [한국어 가이드](https://cathy-kim.github.io/jev-workflow/guide/)에서 전체 개념과 도입 절차를 읽을 수 있습니다.

## License

MIT for this repository's authored code and documentation. See [LICENSE](LICENSE). Referenced third-party services, documentation and models are not relicensed by this project.
