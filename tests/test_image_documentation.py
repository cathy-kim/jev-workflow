"""Offline documentation regressions; no provider requests or real media fixtures."""
import json
from pathlib import Path
import re
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'plugins/jev/skills/jev-decisions'


class ImageDocumentationTests(unittest.TestCase):
    def test_public_contract_snapshot_and_refresh_checklist(self):
        text = (SKILL / 'references/typesafe-contract.md').read_text(encoding='utf-8')
        for phrase in (
            '2026-10-21', 'jev-1.13.0', 'jev-1.14.0',
            'TypeSafe-Danger-Zone-Images: true', 'every request',
            'Dreamer-ready', 'not production-ready', 'PNG', 'JPEG',
            'state', 'instructions', 'criteria', 'top', 'bottom', 'left', 'right',
            '0..1', 'same request', 'no not-found', 'no criteria',
            'no recommended confidence threshold', 'response.model',
            'Version refresh checklist', 'regression', 'PDF', 'ZIP',
            'https://docs.typesafe.ai/images', 'https://docs.typesafe.ai/go/box',
            'https://docs.typesafe.ai/models', 'text-only',
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        skill = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('references/typesafe-contract.md#version-refresh-checklist', skill)

    def test_report_version_tables_and_bounded_refresh(self):
        for name in ('report/guide.html', 'docs/guide/index.html'):
            text = (ROOT / name).read_text(encoding='utf-8')
            for number in (11, 20):
                page = re.search(r'<section class="page" id="p' + str(number) + r'">.*?</section>', text, re.S).group()
                for phrase in ('2026-10-21', 'jev-1.13.0', 'jev-1.14.0',
                               'TypeSafe-Danger-Zone-Images: true', '매 요청',
                               'Dreamer-ready', 'production-ready',
                               'https://docs.typesafe.ai/images', 'https://docs.typesafe.ai/go/box'):
                    with self.subTest(file=name, page=number, phrase=phrase):
                        self.assertTrue(phrase in page, f'Missing {phrase}')
            self.assertNotIn('Box confidence는 null 허용', text)
            self.assertNotIn('Box confidence는 OpenAPI상 null도 허용', text)
            self.assertNotIn('존재 여부 Noul을 별도 요청', text)
            self.assertIn('전체 보고서를 재검증한 것은 아니다', text)
            self.assertIn('같은 요청', text)

    def test_official_sources_and_generated_copy(self):
        raw = (ROOT / 'report/sources.json').read_bytes()
        self.assertEqual(raw, (ROOT / 'docs/guide/sources.json').read_bytes())
        data = json.loads(raw)
        self.assertIn('2026-10-21', data['scope'])
        sources = {s['id']: s for s in data['sources']}
        for key, url in (('S13', 'https://docs.typesafe.ai/images'),
                         ('S14', 'https://docs.typesafe.ai/go/box')):
            self.assertIn(key, sources)
            self.assertEqual(sources[key]['requested_url'], url)
            self.assertEqual(sources[key]['resolved_url'], url)
            self.assertTrue(sources[key]['findings'])
            self.assertTrue(sources[key]['caveats'])

    def test_patch_version_and_zip_reference_parity(self):
        manifest = json.loads((ROOT / 'plugins/jev/.claude-plugin/plugin.json').read_text(encoding='utf-8'))
        marketplace = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['version'], '1.1.0')
        self.assertEqual(marketplace['metadata']['version'], '1.1.0')
        self.assertEqual(marketplace['plugins'][0]['version'], '1.1.0')
        self.assertIn('version: 1.1.0', (SKILL / 'SKILL.md').read_text(encoding='utf-8'))
        for archive, prefix in (('jev-plugin.zip', 'jev/skills/jev-decisions'),
                                ('jev-decisions-skill.zip', 'jev-decisions')):
            with zipfile.ZipFile(ROOT / 'docs/downloads' / archive) as z:
                for relative in ('SKILL.md', 'references/typesafe-contract.md', 'scripts/decision_kit.py'):
                    self.assertEqual(z.read(prefix + '/' + relative), (SKILL / relative).read_bytes())
                if archive == 'jev-plugin.zip':
                    self.assertEqual(json.loads(z.read('jev/.claude-plugin/plugin.json')), manifest)


if __name__ == '__main__':
    unittest.main()
