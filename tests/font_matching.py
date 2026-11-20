"""Synthetic font regression: compare geometry, reject stylistic substitution, retain spans."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import sys

import pymupdf as fitz
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('font_match', ROOT / 'scripts/match_fonts.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
spec2 = importlib.util.spec_from_file_location('workflow', ROOT / 'scripts/pdf_workflow.py')
workflow = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(workflow)


def make_font(path, name, changed=False, omit_b=False):
    fb = FontBuilder(1000, isTTF=True)
    order = ['.notdef', 'A', 'B']
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({65: 'A', **({} if omit_b else {66: 'B'})})
    glyphs = {}
    for index, n in enumerate(order):
        pen = TTGlyphPen(None)
        pen.moveTo((50, 0)); pen.lineTo((500, 0)); pen.lineTo((250, 700 if not changed else 620)); pen.closePath()
        glyphs[n] = pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (600, 50) for n in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({'familyName': name, 'styleName': 'Regular',
                       'uniqueFontIdentifier': name, 'fullName': name,
                       'psName': name.replace(' ', '')})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost(); fb.setupMaxp()
    fb.font['OS/2'].panose.bFamilyType = 2
    fb.font['OS/2'].panose.bSerifStyle = 2
    fb.save(path)


with tempfile.TemporaryDirectory() as temp:
    p = Path(temp); good = p / 'good'; good.mkdir(); bad = p / 'bad'; bad.mkdir()
    make_font(p / 'source.ttf', 'Source Mincho')
    make_font(good / 'renamed.ttf', 'Renamed Mincho')
    make_font(bad / 'wrong.ttf', 'Source Mincho', changed=True)
    doc = fitz.open(); page = doc.new_page()
    page.insert_font(fontname='custom', fontfile=str(p / 'source.ttf'))
    page.insert_text((50, 90), 'AB', fontname='custom', fontsize=25)
    pdf = p / 'source.pdf'; doc.save(pdf)
    mapping, report = module.match(pdf, [good], {})
    assert mapping and report['complete']
    assert report['fonts'][0]['status'] == 'used_glyphs_and_advances_equal'
    assert report['fonts'][0]['verified_unique_glyphs'] == 2
    source_name = report['fonts'][0]['source_font']
    mapping, report = module.match(pdf, [bad], {source_name: 'Hiragino Sans GB'})
    assert not mapping and report['fonts'][0]['status'] == 'rejected_style_mismatch'
    assert not report['complete']
    duplicate = fitz.open()
    for index, fontfile in enumerate([p / 'source.ttf', bad / 'wrong.ttf']):
        page = duplicate.new_page()
        page.insert_font(fontname=f'custom{index}', fontfile=str(fontfile))
        page.insert_text((50, 90), 'AB', fontname=f'custom{index}', fontsize=25)
    duplicate.save(p / 'duplicate.pdf')
    mapping, report = module.match(p / 'duplicate.pdf', [good], {})
    assert not mapping and report['warnings']
    missing = p / 'missing'; missing.mkdir(); make_font(missing / 'missing.ttf', 'Missing Mincho', omit_b=True)
    mapping, report = module.match(pdf, [missing], {})
    assert not mapping and not report['complete']
    mixed = fitz.open(); page = mixed.new_page()
    page.insert_text((50, 90), 'Hello', fontname='hebo', fontsize=20)
    page.insert_text((110, 90), 'World', fontname='tiit', fontsize=18)
    mixed.save(p / 'mixed.pdf')
    (p / 'map.json').write_text(json.dumps({'Helvetica-Bold': 'Arial', 'Times-Italic': 'Times New Roman'}))
    out = p / 'ppt'; out.mkdir()
    workflow.prepare_ppt(p / 'mixed.pdf', out, p / 'map.json')
    groups = json.loads((out / 'ppt-manifest.json').read_text())['pages'][0]['text']
    spans = [run for group in groups for run in group['runs']]
    assert any(x['text'] == 'Hello' and x['bold'] and x['font'] == 'Arial' for x in spans)
    assert any(x['text'] == 'World' and x['italic'] and x['font'] == 'Times New Roman' for x in spans)
print(json.dumps({'result': 'pass', 'checks': ['renamed equivalent glyph geometry', 'wrong geometry not accepted as identity', 'serif to sans rejected', 'ambiguous subsets not certified', 'missing character coverage rejected', 'mixed fonts and emphasis preserved']}))
