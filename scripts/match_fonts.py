#!/usr/bin/env python3
"""Match complete supplied fonts to embedded PDF glyphs; audit explicit fallbacks."""
import argparse
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import re

import pymupdf as fitz
from fontTools.ttLib import TTFont, TTCollection
from fontTools.pens.recordingPen import DecomposingRecordingPen


def norm(name):
    return re.sub(r'[^a-z0-9]', '', re.sub(r'^[A-Z]{6}\+', '', name).lower())


def metadata(font):
    names = {n.toUnicode() for n in font['name'].names if n.nameID in (1, 2, 4, 6, 16, 17)}
    family = next((n.toUnicode() for n in font['name'].names
                   if n.nameID == 1 and n.platformID == 3 and n.langID == 1033), None)
    family = family or next(n.toUnicode() for n in font['name'].names if n.nameID == 1)
    os2 = font.get('OS/2')
    serif = os2.panose.bSerifStyle if os2 else 0
    kind = 'serif' if 2 <= serif <= 10 else 'sans' if 11 <= serif <= 15 else 'unknown'
    return family, names, kind


def classify_name(name):
    n = norm(name)
    if any(x in n for x in ('mincho', 'mingliu', 'songti', 'simsun', 'serif', 'times')):
        return 'serif'
    if any(x in n for x in ('gothic', 'sans', 'hei', 'helvetica', 'arial', 'halis')):
        return 'sans'
    return 'unknown'


def signature(font, glyph):
    gs = font.getGlyphSet()
    pen = DecomposingRecordingPen(gs)
    gs[glyph].draw(pen)
    upem = font['head'].unitsPerEm
    def scaled(value):
        if isinstance(value, (tuple, list)):
            return tuple(scaled(v) for v in value)
        if isinstance(value, (float, int)):
            return round(value / upem, 6)
        return value
    return scaled(pen.value), round(gs[glyph].width / upem, 6)


def match(source, dirs, fallbacks):
    doc = fitz.open(source)
    if doc.needs_pass:
        raise ValueError('Opening password required.')
    used = defaultdict(dict)
    for page in doc:
        for span in page.get_texttrace():
            for ch in span['chars']:
                # MuPDF glyph IDs address the embedded font, not PDF CIDs.
                if ch[0] >= 32:
                    used[span['font']][(ch[0], ch[1])] = None
    embedded = {}
    embedded_payloads = {}
    source_aliases = defaultdict(set)
    ambiguous = set()
    for page in doc:
        for row in page.get_fonts(full=True):
            name, ext, _, blob = doc.extract_font(row[0])
            if blob and ext in ('ttf', 'otf'):
                try:
                    font = TTFont(io.BytesIO(blob))
                    key = norm(name)
                    payload = hashlib.sha256(blob).hexdigest()
                    if key in embedded_payloads and embedded_payloads[key] != payload:
                        ambiguous.add(key)
                    embedded_payloads[key] = payload
                    embedded[key] = font
                    source_aliases[key].add(key)
                    for entry in font['name'].names:
                        if entry.nameID in (1, 4, 6):
                            alias = norm(entry.toUnicode())
                            source_aliases[key].add(alias)
                            embedded.setdefault(alias, font)
                except Exception:
                    pass
    # Same font name may reference different subsets with unrelated glyph IDs.
    # Do not certify geometry against an arbitrarily chosen subset.
    for key in ambiguous:
        for alias in source_aliases[key]:
            embedded.pop(alias, None)
    candidates = []
    warnings = [{"kind": "ambiguous_embedded_subsets", "font": key,
                 "action": "identity comparison skipped; inspect per-resource glyph mapping"}
                for key in sorted(ambiguous)]
    for folder in dirs:
        for path in sorted(Path(folder).rglob('*')):
            if path.suffix.lower() not in ('.ttf', '.otf', '.ttc'):
                continue
            try:
                fonts = TTCollection(path).fonts if path.suffix.lower() == '.ttc' else [TTFont(path)]
                for face, font in enumerate(fonts):
                    family, names, kind = metadata(font)
                    candidates.append((path, face, font, family, names, kind))
            except Exception as error:
                warnings.append({'file': str(path), 'error': str(error)})
    mapping, audit = {}, []
    for name, chars in used.items():
        original = embedded.get(norm(name))
        source_kind = metadata(original)[2] if original and 'name' in original else 'unknown'
        if source_kind == 'unknown':
            source_kind = classify_name(name)
        exact = []
        for path, face, font, family, names, kind in candidates:
            cmap = font.getBestCmap() or {}
            if not all(code in cmap for code, _ in chars):
                continue
            glyph_matches = 0
            if original:
                try:
                    glyph_matches = sum(signature(original, original.getGlyphName(gid)) ==
                                        signature(font, cmap[code]) for code, gid in chars)
                except Exception:
                    glyph_matches = 0
            if original and glyph_matches == len(chars):
                exact.append((path, face, font, family, names, kind))
        if exact:
            path, face, font, family, names, kind = exact[0]
            mapping[name] = family
            audit.append({'source_font': name, 'target_font': family,
                          'status': 'used_glyphs_and_advances_equal',
                          'verified_unique_glyphs': len(chars),
                          'source_kind': source_kind, 'target_kind': kind,
                          'file': str(path.resolve()), 'face_index': face,
                          'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                          'fsType': font['OS/2'].fsType if 'OS/2' in font else None,
                          'warning': 'Equality covers used glyphs, not every glyph or font version. License and target application must be verified.'})
        else:
            target = fallbacks.get(name)
            target_kind = classify_name(target or '')
            status = 'fallback' if target else 'unresolved'
            if source_kind != 'unknown' and target_kind != 'unknown' and source_kind != target_kind:
                status = 'rejected_style_mismatch'
            if status == 'fallback':
                mapping[name] = target
            audit.append({'source_font': name, 'target_font': target,
                          'status': status, 'source_kind': source_kind,
                          'target_kind': target_kind,
                          'warning': 'Fallback is not an original-font identity match; verify weight, coverage, width and rendering.'})
    return mapping, {'fonts': audit, 'warnings': warnings,
                     'complete': len(mapping) == len(used),
                     'scope': 'Supplied full font files; embedded PDF subsets are only comparison references. No automatic font download or installation.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--font-dir', type=Path, action='append', required=True)
    parser.add_argument('--fallback-map', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Output already exists.')
    fallbacks = json.loads(args.fallback_map.read_text()) if args.fallback_map else {}
    mapping, audit = match(args.source, args.font_dir, fallbacks)
    args.output.mkdir(parents=True)
    for filename, value in [('font-map.json', mapping), ('font-audit.json', audit)]:
        (args.output / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2))
    print(json.dumps({'complete': audit['complete'], 'fonts': len(audit['fonts'])}))
    return 0 if audit['complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
