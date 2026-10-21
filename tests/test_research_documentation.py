"""Public research provenance, packaging and scope regression checks."""
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'plugins/jev/skills/jev-decisions'
REFS = SKILL / 'references'


class ResearchDocumentationTests(unittest.TestCase):
    def test_catalog_is_pinned_and_public(self):
        data = json.loads((REFS / 'research-sources.json').read_text())
        self.assertEqual(data['schema_version'], 'research-sources/v1')
        self.assertEqual({m['id'] for m in data['models']}, {'videojev', 'mjev-spatial', 'jeva'})
        approved = {
            'github.com/MCG-NJU/VideoJev', 'github.com/Fr0zenCrane/MJev-Spatial',
            'github.com/LiQiiiii/Jeva', 'github.com/InternLM/xtuner',
            'huggingface.co/ZhuYuhan/VideoJev-4B', 'huggingface.co/ZhuYuhan/VideoJev-35B-A3B',
            'huggingface.co/mindlab-research/MJev-Spatial-4B',
            'huggingface.co/Qwen/Qwen3.5-4B', 'huggingface.co/LIQIIIII/Jeva-4B',
        }
        for model in data['models']:
            self.assertRegex(model['paper'], r'^https://arxiv\.org/html/2610\.\d+v1$')
            self.assertRegex(model['code_revision'], r'^[0-9a-f]{40}$')
            text = (REFS / model['reference']).read_text()
            self.assertIn(model['code_revision'], text)
            self.assertNotEqual(model['runtime_status'], 'verified')
            revisions = set()
            for artifact in model['public_artifacts']:
                self.assertRegex(artifact['revision'], r'^[0-9a-f]{40}$')
                url = urlsplit(artifact['url'])
                self.assertEqual(url.scheme, 'https')
                root, revision = url.path.rsplit('/tree/', 1)
                self.assertIn(url.netloc + root, approved)
                self.assertEqual(revision, artifact['revision'])
                revisions.add(revision)
            self.assertEqual(set(re.findall(r'\b[0-9a-f]{40}\b', text)), revisions)

    def test_references_are_full_source_reviews(self):
        for name in ('videojev.md', 'mjev-spatial.md', 'jeva.md'):
            text = (REFS / name).read_text()
            self.assertGreater(len(text), 10000)
            self.assertIn('https://arxiv.org/', text)
            self.assertIn('/blob/', text)
            self.assertRegex(text, r'#L\d+')
            self.assertIn('license', text.lower())
            self.assertRegex(text.lower(), r'not (?:been )?(?:run|executed|reproduced)|unreproduced')
            for forbidden in ('linkedin.com/safety/', '/Users/', '/home/', 'file://', '«redacted:'):
                self.assertNotIn(forbidden, text)

    def test_bundles_and_site_have_identical_references(self):
        names = ('research-models.md', 'research-sources.json', 'videojev.md', 'mjev-spatial.md', 'jeva.md')
        for name in names:
            self.assertEqual((REFS / name).read_bytes(), (ROOT / 'docs/research/references' / name).read_bytes())
        for archive, prefix in (('jev-plugin.zip', 'jev/skills/jev-decisions'), ('jev-decisions-skill.zip', 'jev-decisions')):
            with zipfile.ZipFile(ROOT / 'docs/downloads' / archive) as z:
                for name in names:
                    self.assertEqual((REFS / name).read_bytes(), z.read(prefix + '/references/' + name))
                self.assertEqual((SKILL / 'scripts/research_kit.py').read_bytes(), z.read(prefix + '/scripts/research_kit.py'))

    def test_full_guide_includes_authored_research_chapter(self):
        chapter = (ROOT / 'report/research-chapter.html').read_text(encoding='utf-8').strip()
        for name in ('report/guide.html', 'docs/guide/index.html'):
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertEqual(text.count('<!-- RESEARCH_CHAPTER_START -->'), 1)
            self.assertIn(chapter, text)
            self.assertEqual(re.findall(r'<section class="page" id="(p\d+)"', text), [f'p{i}' for i in range(1, 44)])
            self.assertEqual(len(re.findall(r'<span>\d{1,2} / 43</span></footer>', text)), 43)
            self.assertIn('href="#p36"', text)
            for paper in ('2610.18615', '2610.22276', '2610.18773'):
                self.assertIn('https://arxiv.org/abs/' + paper, text)
        ledger = json.loads((ROOT / 'report/sources.json').read_text(encoding='utf-8'))
        by_id = {item['id']: item for item in ledger['sources']}
        self.assertEqual(len(by_id), len(ledger['sources']))
        for code, paper in (('R9', 'P6'), ('R10', 'P7'), ('R11', 'P8')):
            self.assertIn('/tree/', by_id[code]['resolved_url'])
            self.assertIn('/html/', by_id[paper]['resolved_url'])
        self.assertIn('eight-page', (ROOT / 'README.md').read_text(encoding='utf-8'))
        self.assertIn('version **1.1.0**', (ROOT / 'docs/installation.md').read_text(encoding='utf-8'))

    def test_companion_is_discoverable_and_honest(self):
        page = (ROOT / 'site/research.html').read_text()
        self.assertEqual(page, (ROOT / 'docs/research/index.html').read_text())
        for model in ('VideoJev', 'MJev-Spatial', 'Jeva'):
            self.assertIn(model, page)
        self.assertIn('VALID_CONTRACT_ONLY', page)
        self.assertIn('실행 검증하지 않았다', page)
        self.assertIn('모델 실행 adapter', page)
        for name in ('site/index.html', 'docs/index.html'):
            self.assertIn('href="research/"', (ROOT / name).read_text())
        self.assertIn('references/research-models.md', (SKILL / 'SKILL.md').read_text())


if __name__ == '__main__':
    unittest.main()
