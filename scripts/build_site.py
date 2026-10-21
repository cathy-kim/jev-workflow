#!/usr/bin/env python3
"""Build the static site and deterministic portable bundles. No network access."""
from pathlib import Path
import shutil
import zipfile
from sync_research_chapter import sync

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

WEB_CSS = """
@media screen {
  .reader-nav{max-width:794px;margin:24px auto;padding:16px 24px;font:14px/1.6 Arial,sans-serif;display:flex;flex-wrap:wrap;gap:20px}
  .page{height:auto;min-height:297mm;padding-bottom:72px}
  .footer{position:static!important;margin-top:32px!important}
}
@media screen and (max-width:840px) {
  body{overflow-wrap:anywhere}
  .page{width:calc(100% - 24px);min-height:0;margin:12px;padding:32px 20px;box-shadow:none}
  .page:before{left:20px;right:20px;top:14px}
  h1{font-size:44px;letter-spacing:-1px}h2{font-size:25px}
  p,li{font-size:15px}table{font-size:12px}th,td{padding:8px 5px}
  .footer{gap:12px;flex-wrap:wrap}.toc{columns:1!important;grid-template-columns:1fr!important}
  pre{font-size:12px;padding:12px}figure{overflow-x:auto}
  figure svg{min-width:550px;width:100%;max-width:none}
  a{overflow-wrap:anywhere}
}
@media print{.reader-nav{display:none}}
"""


# Explicit publication inventory: unexpected files are never added to downloads.
PUBLIC_SKILL_FILES = frozenset({
    "SKILL.md",
    "references/implementation-playbook.md",
    "references/offline-starter.md",
    "references/providers-evaluation.md",
    "references/typesafe-contract.md",
    "references/research-models.md",
    "references/research-sources.json",
    "references/videojev.md",
    "references/mjev-spatial.md",
    "references/jeva.md",
    "scripts/research_kit.py",
    "scripts/decision_kit.py",
    "scripts/test_decision_kit.py",
    "scripts/examples/design.md",
    "scripts/examples/policy.json",
    "scripts/examples/policy.synthetic-high-impact.json",
    "scripts/examples/policy.synthetic-recommend.json",
    "scripts/examples/request.json",
    "scripts/examples/response.malformed.synthetic.json",
    "scripts/examples/response.synthetic.json",
    "scripts/examples/rubric.json",
    "templates/design-brief.md",
    "templates/evaluation-record.json",
    "templates/question-registry.json",
})


def bundle(path: Path, sources: list[tuple[Path, str]], *, allowed: set[str]) -> None:
    included: set[str] = set()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, prefix in sources:
            entries = [source] if source.is_file() else sorted(source.rglob("*"))
            for entry in entries:
                if not entry.is_file() or entry.is_symlink():
                    continue
                if "__pycache__" in entry.parts or entry.suffix == ".pyc":
                    continue
                name = prefix if source.is_file() else f"{prefix}/{entry.relative_to(source).as_posix()}"
                if name not in allowed:
                    continue
                included.add(name)
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, entry.read_bytes())
    if included != allowed:
        raise ValueError(f"Missing approved bundle files: {sorted(allowed - included)}")


def main() -> None:
    sync()
    (DOCS / "guide").mkdir(parents=True, exist_ok=True)
    (DOCS / "downloads").mkdir(exist_ok=True)
    (DOCS / ".nojekyll").touch()
    shutil.copyfile(ROOT / "site/index.html", DOCS / "index.html")
    research = DOCS / "research"
    (research / "references").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "site/research.html", research / "index.html")
    references = ROOT / "plugins/jev/skills/jev-decisions/references"
    for name in ("videojev.md", "mjev-spatial.md", "jeva.md", "research-models.md", "research-sources.json"):
        source_file = references / name
        if source_file.is_symlink() or not source_file.is_file():
            raise ValueError(f"Research reference must be an approved regular file: {name}")
        shutil.copyfile(source_file, research / "references" / name)
    source = (ROOT / "report/guide.html").read_text(encoding="utf-8")
    source = source.replace("</head>", f"<style>{WEB_CSS}</style></head>", 1)
    nav = '<nav class="reader-nav" aria-label="Guide navigation"><a href="../">← Jev Workflow</a><a href="../downloads/Jev-Workflow-Guide.pdf">PDF ↓</a><a href="#p2">Contents / 목차</a><a href="../research/">Research models</a><span>Public edition · technical snapshot, not live API verification</span></nav>'
    source = source.replace("<body>", "<body>" + nav, 1)
    (DOCS / "guide/index.html").write_text(source, encoding="utf-8")
    shutil.copyfile(ROOT / "report/sources.json", DOCS / "guide/sources.json")
    license_path = ROOT / "LICENSE"
    skill = ROOT / "plugins/jev/skills/jev-decisions"
    if not license_path.is_file() or not (skill / "SKILL.md").is_file():
        raise SystemExit("Plugin and license must exist before building download bundles")
    plugin_allowed = {f"jev/skills/jev-decisions/{name}" for name in PUBLIC_SKILL_FILES}
    plugin_allowed |= {"jev/.claude-plugin/plugin.json", "jev/LICENSE"}
    skill_allowed = {f"jev-decisions/{name}" for name in PUBLIC_SKILL_FILES} | {"jev-decisions/LICENSE"}
    bundle(DOCS / "downloads/jev-plugin.zip", [(ROOT / "plugins/jev", "jev"), (license_path, "jev/LICENSE")], allowed=plugin_allowed)
    bundle(DOCS / "downloads/jev-decisions-skill.zip", [(skill, "jev-decisions"), (license_path, "jev-decisions/LICENSE")], allowed=skill_allowed)
    print("Built docs/index.html, guide, source references and portable bundles.")


if __name__ == "__main__":
    main()
