// Render the GitHub README and check that every image actually loads.
// naturalWidth is only trustworthy after scrolling: GitHub lazy-loads images.
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge' });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const url = 'https://github.com/linluozi/python-constraint-solver-opt';
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForSelector('article', { timeout: 60000 });

  // scroll through the whole readme so lazy images get a chance to load
  await page.evaluate(async () => {
    const step = 400;
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise(r => setTimeout(r, 120));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(3000);

  const imgs = await page.$$eval('article img', els =>
    els.map(e => ({
      src: e.currentSrc || e.src,
      alt: e.alt,
      w: e.naturalWidth,
      h: e.naturalHeight,
      complete: e.complete,
    }))
  );

  console.log('images found:', imgs.length);
  for (const i of imgs) {
    console.log(`  ${i.w > 0 ? 'OK  ' : 'FAIL'} ${i.w}x${i.h}  ${i.alt || '(no alt)'}  ${i.src.slice(0, 110)}`);
  }
  const bad = imgs.filter(i => !i.w);
  console.log('broken:', bad.length);

  await page.screenshot({ path: process.argv[2] || 'readme.png', fullPage: false });
  await browser.close();
  process.exit(bad.length ? 1 : 0);
})();
