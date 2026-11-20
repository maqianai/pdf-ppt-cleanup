"""Paragraph-level editing and distributor-boilerplate regression."""
import collections
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as E
import pymupdf as fitz
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import pdf_workflow as workflow
from paragraphs import paragraphs


def line(text, x, y, width=160, font='Helvetica', size=12, bold=False):
    span = {'text': text, 'bbox': [x, y-size, x+width, y+3], 'size': size,
            'baseline': y, 'color': 0, 'font': 'Arial', 'original_font': font,
            'bold': bold, 'italic': False}
    return {'text': text, 'bbox': span['bbox'], 'baseline': y, 'runs': [span]}


# Cross-block lines merge, columns and unrelated titles do not.
rows = [line('Left first', 30, 70), line('Right first', 330, 70),
        line('Left next', 30, 85), line('Right next', 330, 85),
        line('Heading', 30, 40, size=24)]
groups = paragraphs(rows)
assert len(groups) == 3
assert sorted(x['source_lines'] for x in groups) == [1, 2, 2]
assert all(not ('Left' in x['text'] and 'Right' in x['text']) for x in groups)
centered = paragraphs([line('Long line', 40, 70, 200), line('End.', 100, 85, 80)])
assert len(centered) == 1 and centered[0]['align'] == 'center'

with tempfile.TemporaryDirectory() as temp:
    p = Path(temp); doc = fitz.open(); page = doc.new_page(width=720, height=405)
    page.insert_text((60, 90), 'Brand paragraph first line', fontsize=14)
    page.insert_text((60, 108), 'Second editable line', fontsize=14)
    page.insert_text((60, 360), '* 本手册为某资料库会员私享栏目', fontname='china-s', fontsize=7)
    page.insert_text((60, 372), '独家发布·严禁外传', fontname='china-s', fontsize=7)
    page.insert_text((480, 390), 'Brand copyright 2026. All rights reserved.', fontsize=7)
    source = p/'source.pdf'; doc.save(source)
    candidates = workflow.marketing_candidates(doc[0])
    assert len(candidates) == 2
    assert all(r['category'] == 'distributor_promotion' for r in candidates)
    mapping = p/'fonts.json'; mapping.write_text(json.dumps({'Helvetica': 'Arial', 'Heiti': 'Arial'}))
    blocked = p/'blocked'; blocked.mkdir()
    try:
        workflow.prepare_ppt(source, blocked, mapping)
        raise AssertionError('Uncleaned input must be blocked before fonts or PPT generation.')
    except ValueError as error:
        assert 'Promotional-text candidates remain' in str(error)
    assert not (blocked/'ppt-manifest.json').exists()
    original=p/'original';original.mkdir()
    workflow.prepare_ppt(source,original,mapping,allow_promotional_text=True)
    assert json.loads((original/'ppt-manifest.json').read_text())['content_status']=='original_content_with_promotional_candidates'
    plan = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'text_removals': [{'pages':[1], 'text':r['text'], 'expected_rectangles_per_page':len(doc[0].search_for(r['text'],flags=workflow.TEXT_SEARCH_FLAGS))} for r in candidates]}
    (p/'plan.json').write_text(json.dumps(plan)); clean=p/'clean';clean.mkdir()
    assert workflow.clean(source,clean,p/'plan.json')
    after=fitz.open(clean/'clean.pdf')
    assert '会员私享' not in after[0].get_text() and '严禁外传' not in after[0].get_text()
    assert 'All rights reserved.' in after[0].get_text()
    ppt=p/'ppt';ppt.mkdir();workflow.prepare_ppt(clean/'clean.pdf',ppt,mapping)
    m=json.loads((ppt/'ppt-manifest.json').read_text()); body=[x for x in m['pages'][0]['text'] if 'Brand paragraph' in x['text']]
    assert len(body)==1 and body[0]['source_lines']==2
    subprocess.run([os.environ.get('NODE','node'),str(ROOT/'scripts/build_ppt.cjs'),str(ppt/'ppt-manifest.json'),str(p/'test.pptx')],check=True)
    ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
    with zipfile.ZipFile(p/'test.pptx') as z:
        root=E.fromstring(z.read('ppt/slides/slide1.xml'))
        shapes=[s for s in root.findall('.//p:sp',ns) if 'Brand paragraph' in ''.join(s.itertext())]
        assert len(shapes)==1
        assert len(shapes[0].findall('.//a:p',ns))==1
        assert len(shapes[0].findall('.//a:br',ns))==1
print(json.dumps({'result':'pass','checks':['cross-block paragraph merge','columns kept separate','centered final line','one native shape and paragraph with rich runs','distributor footer classified','uncleaned conversion blocked','footer removed','ordinary brand copyright retained']}))
