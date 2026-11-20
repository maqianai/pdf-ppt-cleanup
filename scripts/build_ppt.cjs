#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const PptxGenJS = require('pptxgenjs');

async function main() {
  const [manifestPath, outputPath] = process.argv.slice(2);
  if (!manifestPath || !outputPath) throw new Error('Usage: node scripts/build_ppt.cjs manifest.json output.pptx');
  if (fs.existsSync(outputPath)) throw new Error('Output already exists.');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const ppt = new PptxGenJS();
  const width = manifest.pages[0].width;
  const height = manifest.pages[0].height;
  ppt.defineLayout({ name: 'SOURCE', width: width / 72, height: height / 72 });
  ppt.layout = 'SOURCE';
  for (const page of manifest.pages) {
    const slide = ppt.addSlide();
    const scale = Math.min(width / page.width, height / page.height);
    const offsetX = (width - page.width * scale) / 2;
    const offsetY = (height - page.height * scale) / 2;
    slide.addImage({
      path: path.resolve(path.dirname(manifestPath), page.background),
      x: offsetX / 72, y: offsetY / 72,
      w: page.width * scale / 72, h: page.height * scale / 72,
    });
    for (const item of page.text) {
      const [left, , right, bottom] = item.bbox;
      const top = item.baseline - item.size;
      slide.addText(item.text, {
        x: (offsetX + left * scale) / 72,
        y: (offsetY + top * scale) / 72,
        w: Math.max(1, Math.min(page.width - left, right - left + 3)) * scale / 72,
        h: Math.max(item.size * 1.5, bottom - top) * scale / 72,
        fontFace: item.font, fontSize: item.size * scale,
        bold: item.bold || false, italic: item.italic || false,
        color: item.color.toString(16).padStart(6, '0'),
        margin: 0, breakLine: false, wrap: false, valign: 'top',
      });
    }
  }
  await ppt.writeFile({ fileName: outputPath });
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
