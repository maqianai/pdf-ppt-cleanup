# Validation

2026-11-19 · release candidate 1.0.0

## Executed

A clean Python virtual environment installed PyMuPDF 1.28.2 from requirements.txt. npm installed PptxGenJS 4.0.1 with a generated package-lock.json. The bundled runtime also passed the same smoke test with PyMuPDF 1.26.7.

The synthetic fixture has three pages, an independent annotation, a vector rectangle, native text and an unrelated advertising page. It is generated at runtime.

Passed checks:

- Inspection CLI exposes page resources and previews.
- Input SHA256 validation rejects a mismatched plan.
- Explicit whole-page deletion retains page order.
- Explicit annotation deletion removes the target.
- Retained page sizes, font payloads, image payloads and page content streams match the input.
- Input file hash remains unchanged.
- Nonempty output directories are rejected.
- Editable extraction creates native text records.
- Node builder exports a readable PPTX package with two slides and native text.

## Boundaries

This release's public test did not execute real PowerPoint editing, save/reopen, PDF export, font embedding, OCR or cross-platform visual rendering.

Agent semantic review selects whole-page advertising and individual cleanup targets. The scripts execute the explicit reviewed plan. Text extraction creates per-line candidates that still need paragraph organization, complex style repair and visual review.

The public package includes no user documents, commercial font files or task-specific page numbers. Input hash and object fingerprints prevent accidentally applying an old document's cleanup plan to a new document.

HTML output includes source and cleaned page previews, which may contain sensitive source content. The agent should deliver it to the user under the same handling rules as the input PDF.


## v1.1.0 regression · 2026-11-19

Executed the original smoke suite and the new text cleanup suite on PyMuPDF 1.28.2, then repeated text cleanup on 1.26.7.

The new synthetic regression verifies repeated ordinary-text footers and inline promotion text, exit code 2 and an HTML warning for an incomplete plan, full cleanup after explicit text targets, retained brand text, image bytes, font bytes and vector/image rendering. Wrong match counts are rejected.

A private 10-page real-document regression used the same public CLI without the former document-specific stream-patching helper. It removed 20 footer lines, 3 inline promotion phrases and 6 advertising annotations. Native-text residual candidates were zero. Font/image payload and page-size checks passed. Source remained unchanged. The private PDF, cleanup plan and screenshots are excluded from the public repository.

This release does not claim universal marketing-text detection, pixel-perfect rendering, OCR coverage or full editable-PPT font fidelity.
