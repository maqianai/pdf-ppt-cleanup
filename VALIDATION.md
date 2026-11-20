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


## v1.2.0 font regression · 2026-11-20

Ran smoke.py, text_cleanup.py and font_matching.py on PyMuPDF 1.28.2 / fontTools 4.68.0. The new generated TTF fixtures verify renamed but equal glyph geometry, rejection of different geometry with the same name, rejection of serif-to-sans fallback, missing character coverage, and mixed font/bold/italic extraction. The CLI automatically applies its bundled complete-font geometry check during prepare-ppt.

A private single-page regression used an existing brand PDF. The included official OFL BIZ UDPMincho Regular matched all 7 distinct title glyphs (8 occurrences) and their advances from the PDF's embedded BIZ-UDPMincho-Medium. The two-row native title was generated automatically. Mac PowerPoint 16.114.1 initially fell back to Microsoft YaHei until its font cache was refreshed by restarting the application. The subsequent local PDF export actually used BIZUDPMincho-Regular, with 7/7 title glyph outlines and advances matching the source. The same page from Convertio used MingLiU and lost its wood-grain background. This is a private title-specific result, not a universal converter ranking or an all-page fidelity claim.

Actual PowerPoint UI changed the first title to four previously unused characters, saved a separate PPTX, closed and reopened it, then exported PDF. The new characters remained native text in BIZUDPMincho-Regular and the replaced title was absent. The user documents and screenshots stay outside this repository.

Remaining: the other font families on this private page still use disclosed substitutes; background color and text placement differ; semantic paragraph grouping remains necessary. Font embedding inside PPTX is not implemented. A receiving machine must install the supplied licensed font. Full-font coverage, shaping/kerning, non-TTF/CFF resources, other operating systems and other documents are not universally certified.


## v1.3.0 paragraphs and distribution boilerplate · 2026-11-20

The new paragraph_cleanup.py fixture verifies cross-block line grouping, keeping columns separate, a centered short final line, one native PPT shape and paragraph with rich runs and soft breaks, classification/removal of member-distribution footers, blocking an uncleaned PDF before font conversion, and retaining ordinary brand copyright. Existing smoke, text cleanup and font matching suites remain required.

A private single-page regression removed two distributor-boilerplate footer lines via an explicit reviewed plan. In actual PowerPoint, Chinese body text changed from 14 fragment shapes to 1 rich-text shape, English body from 5 to 1; the title and subtitle are separate shapes (4 total). A screenshot verified that selecting the Chinese body selects all three source lines at once. Local PowerPoint PDF export was visually checked for overlap and text completeness.

The builder preserves source soft breaks and disables automatic wrapping to prevent substitute-font wrapping from doubling lines. This improves whole-paragraph selection/editing but does not recreate a word processor's natural paragraph reflow. Long inserted text may need box resizing or explicit wrapping and visual verification. Font substitution/color differences and font-embedding limits from v1.2.0 remain.
