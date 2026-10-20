#!/usr/bin/env python3
"""Render the public report with Playwright. Optional tooling, no provider calls."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Optional path to an existing Chromium/Chrome executable")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/downloads/Jev-Workflow-Guide.pdf")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        options = {"headless": True}
        if args.browser:
            options["executable_path"] = args.browser
        browser = p.chromium.launch(**options)
        page = browser.new_page(viewport={"width": 1100, "height": 1300})
        page.goto((ROOT / "report/guide.html").as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        qa = page.evaluate("""() => ({
          pages:document.querySelectorAll('.page').length,
          svg:document.querySelectorAll('svg').length,
          overlap:[...document.querySelectorAll('.page')].filter(s=>{
            const m=s.querySelector('main'),f=s.querySelector('footer');
            return m && f && m.getBoundingClientRect().bottom>f.getBoundingClientRect().top-4;
          }).map(s=>s.id)
        })""")
        if qa["overlap"]:
            raise SystemExit(f"Report layout overlap: {qa['overlap']}")
        page.pdf(path=str(args.output), prefer_css_page_size=True, print_background=True, tagged=True, outline=True)
        browser.close()
    print(json.dumps(qa))
    print("PDF written:", args.output.name)


if __name__ == "__main__":
    main()
