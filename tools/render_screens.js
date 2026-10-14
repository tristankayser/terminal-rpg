#!/usr/bin/env node
// tools/render_screens.js — render terminal HTML dumps to PNG.
// Usage: node tools/render_screens.js <out_dir> <file.html> [...]
// Called by tools/screenshots.py; needs the `playwright` package + Chromium.
const path = require("path");

let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (e) {
  ({ chromium } = require("/opt/node-tools/node_modules/playwright"));
}

(async () => {
  const [outDir, ...files] = process.argv.slice(2);
  if (!outDir || !files.length) {
    console.error("usage: render_screens.js <out_dir> <file.html> ...");
    process.exit(2);
  }
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1.5, viewport: { width: 1200, height: 900 } });
  for (const f of files) {
    await page.goto("file://" + path.resolve(f));
    await page.evaluate(() => document.fonts.ready);
    const out = path.join(outDir, path.basename(f).replace(/\.html$/, ".png"));
    await page.locator("body").screenshot({ path: out, omitBackground: true });
    console.log("wrote", out);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
