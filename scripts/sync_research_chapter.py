#!/usr/bin/env python3
"""Synchronize the authored research chapter into the full public HTML guide."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
START = '<!-- RESEARCH_CHAPTER_START -->'
END = '<!-- RESEARCH_CHAPTER_END -->'
TOC = '<a href="#p36"><span>연구 확장: VideoJev · MJev-Spatial · Jeva</span><span class="num">36–43</span></a>'


def sync() -> None:
    path = ROOT / 'report/guide.html'
    guide = path.read_text(encoding='utf-8')
    chapter = (ROOT / 'report/research-chapter.html').read_text(encoding='utf-8').strip()
    ids = re.findall(r'<section class="page" id="(p\d+)"', chapter)
    if ids != [f'p{i}' for i in range(36, 44)]:
        raise ValueError('Research chapter must contain exactly ordered p36-p43')
    block = START + '\n' + chapter + '\n' + END
    if START in guide or END in guide:
        if guide.count(START) != 1 or guide.count(END) != 1:
            raise ValueError('Ambiguous research chapter boundaries')
        guide = re.sub(re.escape(START) + r'.*?' + re.escape(END), lambda _: block, guide, flags=re.S)
    else:
        if guide.count('</body></html>') != 1:
            raise ValueError('Missing unique document tail')
        guide = guide.replace('</body></html>', block + '</body></html>')
    if TOC not in guide:
        match = re.search(r'(<section class="page" id="p2">.*?<div class="toc">)(.*?)(</div>)', guide, re.S)
        if not match:
            raise ValueError('Missing table of contents')
        guide = guide[:match.start(3)] + TOC + guide[match.start(3):]
    total = len(re.findall(r'<section class="page" id="p\d+"', guide))
    if total != 43:
        raise ValueError('Unexpected full guide page count')
    guide = re.sub(r'(<span>\d{1,2}) / \d+(</span></footer>)', rf'\g<1> / {total}\2', guide)
    guide = guide.replace('TECHNICAL REPORT · 2026.10.20 · v1.0', 'TECHNICAL REPORT · 2026.10.21 · v1.1')
    guide = guide.replace('JEV / IMPLEMENTATION GUIDE V2 · 2026-10-20', 'JEV / PUBLIC WORKFLOW GUIDE V1.1 · 2026-10-21')
    guide = guide.replace('공급자 교체 · 평가 · 비용 · 운영</li>', '평가·운영 + 영상·공간·null 연구 확장</li>')
    path.write_text(guide, encoding='utf-8')
    print(f'Synchronized {len(ids)} research pages; full guide {total} pages.')


if __name__ == '__main__':
    sync()
