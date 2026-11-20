# Font matching and rendering

## Resolve a complete font before substituting

Use local licensed fonts, the supplied OFL font assets, author-provided fonts, or official vendor repositories. Record the file digest, license and family/style. Do not treat an embedded PDF subset as a complete reusable font: it may lack Unicode mappings or glyphs needed for new text.

```sh
python scripts/match_fonts.py source.pdf font-review \
  --font-dir assets/fonts --font-dir /path/to/other/licensed-fonts \
  --fallback-map reviewed-fallbacks.json
python scripts/pdf_workflow.py prepare-ppt source.pdf ppt-work \
  --font-map font-review/font-map.json
node scripts/build_ppt.cjs ppt-work/ppt-manifest.json editable.pptx
```

`prepare-ppt` also runs this check against `assets/fonts` automatically, using `--font-map` as explicit fallbacks, and writes `font-audit.json`. An incompatible fallback fails before the PPT build. For additional licensed font libraries, first use `match_fonts.py` as above.

`match_fonts.py` reads supplied TTF/OTF/TTC files, checks every used character's coverage, and compares decomposed glyph outlines and advance widths in em units against readable embedded TTF/OTF resources. It does not download or install fonts, embed fonts in PPT, compare kerning/shaping tables, or prove all versions/all glyphs equivalent. Raw CFF/CID resources and cases without readable geometry need other evidence or explicit substitution. Geometry matching is intentionally conservative; a harmless geometry reordering may cause a non-match.

`used_glyphs_and_advances_equal` means only the characters used in this PDF matched. `fallback` remains a disclosed replacement. `rejected_style_mismatch` and `unresolved` produce exit code 2 and an incomplete map, preventing a silent build. A completed map can still include fallbacks and is not a font-fidelity pass.

The matcher uses embedded PANOSE metadata when available and conservative name hints for serif/sans classification. Unknown or inconsistent metadata requires visual review. The `fsType` value is recorded as evidence, not a license decision.

## What the BIZ example taught

An original PDF can call its font `BIZ-UDPMincho-Medium`, while the official open source file is named `BIZUDPMincho-Regular`. The upstream release notes document the historical naming change. Check the actual outlines and widths rather than adding a universal name-only alias.

- Upstream: https://github.com/googlefonts/morisawa-biz-ud-mincho/releases
- Included font provenance: `assets/fonts/biz-udpmincho/SOURCE.json`
- Included license: `assets/fonts/biz-udpmincho/OFL.txt`

Do not assume this font replaces all Chinese fonts. It is a Japanese font; check coverage and regional glyph forms. The candidate is only an identity match where actual source glyphs match.

## Integrate and verify

Use the font's real family name in PPT; retain per-span fonts and emphasis. If distributing a licensed full font beside PPT, include its license. Install/register it using the target OS's supported mechanism, then refresh the target app if needed. On the tested Mac, PowerPoint continued substituting a newly copied font until the app was restarted. Close only task-owned documents; do not disrupt user work.

Open and export in the actual application. Check exported PDF font resources, used glyph geometry, text bounds and typography. Test new characters and save/reopen when editable delivery is being accepted. A successful font lookup or a written PPT font name alone cannot pass validation. If PPT font embedding has not actually been implemented and tested, state that the recipient must install the supplied font; a PDF with embedded used glyphs does not prove the PPT embeds a font.

For comparisons, use the identical input and rendering application. Present aligned text crops separately from page position/background. An identity result for a title does not prove the whole page's fonts, colors, paragraphs or other documents are lossless.
