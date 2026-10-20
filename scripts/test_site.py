"""Static public-site contract tests (stdlib only). Run after build_site.py."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import json
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.ids = set()
        self.pages = 0
        self.svg = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if key in attrs:
                self.hrefs.append(attrs[key])
        if tag == "section" and "page" in attrs.get("class", "").split():
            self.pages += 1
        if tag == "svg":
            self.svg += 1


class SiteTests(unittest.TestCase):
    def test_site_relative_links_and_anchors(self):
        for html in (ROOT / "docs").rglob("*.html"):
            parsed = Links()
            parsed.feed(html.read_text(encoding="utf-8"))
            for href in parsed.hrefs:
                url = urlsplit(href)
                if url.scheme or url.netloc:
                    self.assertIn(url.scheme, {"https", "http", "data", "mailto"})
                    continue
                target = (html.parent / unquote(url.path)).resolve() if url.path else html
                if target.is_dir():
                    target = target / "index.html"
                self.assertTrue(target.is_relative_to(ROOT / "docs"), href)
                self.assertTrue(target.is_file(), f"{html.name}: {href}")
                if url.fragment and target.suffix == ".html":
                    target_parsed = Links()
                    target_parsed.feed(target.read_text(encoding="utf-8"))
                    self.assertIn(unquote(url.fragment), target_parsed.ids, href)

    def test_guide_structure_and_scope(self):
        for name in ["report/guide.html", "docs/guide/index.html"]:
            p = Links()
            text = (ROOT / name).read_text(encoding="utf-8")
            p.feed(text)
            self.assertEqual(p.pages, 35)
            self.assertEqual(p.svg, 11)
            self.assertIn("공개판 범위와 안전한 재사용", text)
            self.assertNotIn("file://", text)

    def test_source_reference_schema(self):
        data = json.loads((ROOT / "report/sources.json").read_text(encoding="utf-8"))
        self.assertTrue(data["sources"])
        for source in data["sources"]:
            self.assertEqual(set(source) - {"id", "title", "requested_url", "resolved_url", "findings", "caveats"}, set())
            self.assertTrue(source["requested_url"].startswith("https://"))

    def test_bundles_contain_skill_and_no_runtime_state(self):
        for filename, root in [("jev-plugin.zip", "jev/skills/jev-decisions"), ("jev-decisions-skill.zip", "jev-decisions")]:
            with zipfile.ZipFile(ROOT / "docs/downloads" / filename) as z:
                names = z.namelist()
                self.assertIn(root + "/SKILL.md", names)
                self.assertIn(root + "/scripts/decision_kit.py", names)
                self.assertFalse(any("__pycache__" in n or "/.git/" in n or n.endswith((".env", ".pyc", ".pem", ".key")) for n in names))
                self.assertFalse(any(n.startswith("/") or ".." in Path(n).parts for n in names))

    def test_pdf_exists(self):
        pdf = (ROOT / "docs/downloads/Jev-Workflow-Guide.pdf").read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 10000)


if __name__ == "__main__":
    unittest.main()
