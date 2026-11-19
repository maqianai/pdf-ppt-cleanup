#!/usr/bin/env python3
"""Portable PDF inspection, reviewed object cleanup and editable PPT preparation."""
import argparse
import base64
import hashlib
import html
import json
from pathlib import Path

import pymupdf as fitz


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def open_pdf(path):
    doc = fitz.open(path)
    if doc.needs_pass:
        raise ValueError("Opening password required. Supply an accessible input PDF.")
    return doc


def inspect(source, output):
    doc = open_pdf(source)
    pages = []
    for index, page in enumerate(doc):
        page.get_pixmap(matrix=fitz.Matrix(1, 1)).save(output / f"page-{index + 1}.png")
        pages.append({
            "page": index + 1,
            "size": list(page.rect),
            "text": page.get_text(),
            "annotations": [
                {"xref": xref, "type": kind, "object": doc.xref_object(xref)}
                for xref, kind, _ in page.annot_xrefs()
            ],
            "forms": [
                {"xref": item[0], "sha256": digest(doc.xref_stream(item[0]) or b"")}
                for item in page.get_xobjects()
            ],
            "fonts": [list(font) for font in page.get_fonts()],
        })
    write_json(output / "inspection.json", {
        "source_sha256": digest(source.read_bytes()), "pages": pages,
        "decision": "Agent reviews page images and records explicit cleanup targets.",
    })


def page_payloads(doc, page):
    return {
        "fonts": sorted(digest(doc.extract_font(font[0])[3])
                        for font in page.get_fonts() if font[0] > 0),
        "images": sorted(digest(doc.extract_image(image[0])["image"])
                         for image in page.get_images()),
        "content": digest(b"".join(doc.xref_stream(xref)
                                  for xref in page.get_contents())),
    }


def clean(source, output, plan_path):
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    source_hash = digest(source.read_bytes())
    if plan["source_sha256"] != source_hash:
        raise ValueError("Source fingerprint mismatch. Inspect this exact input again.")
    doc = open_pdf(source)
    removed = plan.get("delete_pages", [])
    if len(set(removed)) != len(removed):
        raise ValueError("Duplicate deleted pages.")
    if any(not isinstance(n, int) or n < 1 or n > len(doc) for n in removed):
        raise ValueError("Deleted page out of range.")
    kept = [n for n in range(1, len(doc) + 1) if n not in removed]
    if not kept:
        raise ValueError("The plan must retain at least one page.")
    for row in plan.get("annotations", []):
        if not isinstance(row["page"], int) or not 1 <= row["page"] <= len(doc):
            raise ValueError("Annotation page out of range.")
        page = doc[row["page"] - 1]
        actual = {xref for xref, _, _ in page.annot_xrefs()}
        targets = set(row["xrefs"])
        if not targets <= actual:
            raise ValueError("Annotation does not belong to the specified page.")
        retained = sorted(actual - targets)
        doc.xref_set_key(page.xref, "Annots",
                         "[" + " ".join(f"{xref} 0 R" for xref in retained) + "]")
    for row in plan.get("forms", []):
        xref = row["xref"]
        if "/Form" not in doc.xref_object(xref):
            raise ValueError("Target is not a Form.")
        if digest(doc.xref_stream(xref) or b"") != row["sha256"]:
            raise ValueError("Form fingerprint mismatch.")
        doc.update_stream(xref, b"q Q")
    if removed:
        doc.delete_pages(sorted(n - 1 for n in removed))
    result = output / "clean.pdf"
    doc.save(result, garbage=3, deflate=True, encryption=fitz.PDF_ENCRYPT_NONE)
    original = open_pdf(source)
    written = open_pdf(result)
    checks = []
    report = []
    for index, number in enumerate(kept):
        before, after = original[number - 1], written[index]
        old, new = page_payloads(original, before), page_payloads(written, after)
        checks.append({
            "original_page": number, "output_page": index + 1,
            "size_equal": before.rect == after.rect,
            "font_payloads_equal": old["fonts"] == new["fonts"],
            "image_payloads_equal": old["images"] == new["images"],
            "page_content_equal": old["content"] == new["content"],
        })
        figures = []
        for label, page in [("Original", before), ("Clean", after)]:
            image = base64.b64encode(page.get_pixmap().tobytes("png")).decode()
            figures.append(f'<figure><figcaption>{label}</figcaption>'
                           f'<img alt="{label} page {number}" src="data:image/png;base64,{image}"></figure>')
        report.append(f"<h3>Original {number} / Output {index + 1}</h3>"
                      f"<article>{''.join(figures)}</article>")
    write_json(output / "verification.json", {
        "source_sha256": source_hash, "deleted_pages": removed,
        "checks": checks,
        "limits": "Payload checks require visual review and shared Form review. "
                  "PPT, OCR, fonts and cross-application edit tests are separate.",
    })
    summary = html.escape(json.dumps(checks, ensure_ascii=False, indent=2))
    (output / "report.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>PDF cleanup verification</title><style>'
        'body{max-width:1200px;margin:auto;padding:24px;font:16px/1.6 system-ui}'
        'nav{position:sticky;top:0;background:white;padding:12px}'
        'article{display:grid;grid-template-columns:1fr 1fr;gap:12px}'
        'figure{margin:0}img{width:100%}pre{white-space:pre-wrap}'
        '@media(max-width:700px){article{grid-template-columns:1fr}}</style>'
        '<h1>PDF cleanup verification</h1><nav><a href="#checks">Checks</a> · '
        '<a href="#pages">Page comparison</a> · <a href="clean.pdf">Clean PDF</a></nav>'
        '<p>Reviewed object cleanup. Inspect retained content and shared Forms before '
        'claiming lossless preservation. Source file fingerprint is in verification.json.</p>'
        f'<section id="checks"><h2>Checks</h2><pre>{summary}</pre></section>'
        f'<section id="pages"><h2>Comparison</h2>{"".join(report)}</section></html>',
        encoding="utf-8")
    if digest(source.read_bytes()) != source_hash:
        raise ValueError("Source changed during execution.")


def prepare_ppt(source, output, font_map_path):
    font_map = json.loads(font_map_path.read_text(encoding="utf-8"))
    doc = open_pdf(source)
    pages, warnings = [], []
    for index, page in enumerate(doc):
        groups = []
        for block in page.get_text("dict", flags=0)["blocks"]:
            for line in block["lines"]:
                spans = line["spans"]
                text = "".join(span["text"] for span in spans).strip()
                if not text:
                    continue
                style = max(spans, key=lambda span: len(span["text"]))
                original_font = style["font"]
                if original_font not in font_map:
                    raise ValueError(f"Font map missing {original_font!r}; inspect input fonts first.")
                if "\ufffd" in text:
                    warnings.append({"page": index + 1, "kind": "unicode_replacement", "text": text})
                groups.append({
                    "text": text, "bbox": list(line["bbox"]), "size": style["size"],
                    "baseline": style["origin"][1], "color": style["color"],
                    "font": font_map[original_font], "original_font": original_font,
                })
        page.add_redact_annot(page.rect, fill=False)
        page.apply_redactions(images=0, graphics=0, text=0)
        background = output / f"background-{index + 1}.svg"
        background.write_text(page.get_svg_image(text_as_path=True), encoding="utf-8")
        pages.append({"width": page.rect.width, "height": page.rect.height,
                      "background": background.name, "text": groups})
    write_json(output / "ppt-manifest.json", {
        "pages": pages, "warnings": warnings, "font_map": font_map,
        "limitations": [
            "Extracted lines require semantic paragraph grouping and manual correction.",
            "Text already baked into images requires OCR and removal of old image text.",
            "Mapped fonts must be installed and verified in the target presentation app.",
            "Font embedding is not performed by this builder.",
            "SVG background rendering and actual edit behavior need application tests.",
        ],
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["inspect", "clean", "prepare-ppt"])
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--font-map", type=Path)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Use an empty output directory.")
    if args.mode == "clean" and not args.plan:
        parser.error("clean requires --plan")
    if args.mode == "prepare-ppt" and not args.font_map:
        parser.error("prepare-ppt requires --font-map")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.mode == "inspect":
        inspect(args.source, args.output)
    elif args.mode == "clean":
        clean(args.source, args.output, args.plan)
    else:
        prepare_ppt(args.source, args.output, args.font_map)


if __name__ == "__main__":
    main()
