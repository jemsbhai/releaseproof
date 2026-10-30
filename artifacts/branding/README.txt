ReleaseProof submission branding

releaseproof-title.svg: original editable vector source, 1200 x 800 (3:2).
title-card.html: fixed-size browser render wrapper, no external assets.
releaseproof-title-browser.jpg: actual Chrome viewport screenshot.
releaseproof-title.png: the same screenshot pixels encoded as PNG;
317,744 bytes, verified 1200 x 800, below the 5 MB thumbnail limit.

The title card illustrates the product workflow. It contains no fabricated
benchmark, adoption, spending, or safety-certification numbers.

Capture procedure used (Codex CUA browser tools):
1. Serve this folder with Python's http.server bound to 127.0.0.1:7862.
2. Open http://127.0.0.1:7862/title-card.html in a dedicated Chrome tab.
3. Set the browser viewport capability to {width:1200,height:800}.
4. Visually inspect tab.getScreenshot().
5. Save await tab.screenshot({fullPage:false}) with node:fs/promises.writeFile.
   This browser returns JPEG bytes; do not rename those bytes to .png.
6. Encode the saved JPEG to PNG with bundled Pillow Image.open(...).save(...).
7. Reset the viewport capability after capture.

Actual application screenshot assets are under ../screenshots/.
They include controlled synthetic fixture results and are labelled as such.
For a demo video, record the actual application interactions; these stills
can serve as the opening title and visual references, not claimed live runs.
