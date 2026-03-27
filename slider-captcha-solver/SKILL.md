---
name: slider-captcha-solver
description: Solve slider/puzzle CAPTCHA challenges (GeeTest v3/v4, AliCaptcha, DataDome, TikTok, etc.) using OpenCV gap detection and human-like mouse trajectory simulation. Use when encountering slider captchas during web scraping or browser automation. Supports both Chrome MCP browser and Playwright.
---

# Slider CAPTCHA Solver

Solve slider/puzzle CAPTCHAs by detecting the gap position and performing a drag.

## Two Approaches

### Approach 1: In-Browser JS Analysis + Chrome MCP Drag (Preferred)

**Key advantage**: Zero delay between image analysis and drag — no risk of the captcha image refreshing mid-solve.

**Step 1** — Run this JS via `javascript_tool` to analyze the captcha and return coordinates:

```javascript
(function() {
  // 1. Find captcha elements (adapt selectors to captcha type)
  const bgEl = document.querySelector('.geetest_bg')         // GeeTest
            || document.querySelector('[class*="captcha"] img')
            || document.querySelector('canvas.captcha-bg');
  const pieceEl = document.querySelector('.geetest_slice_bg') // GeeTest piece
               || document.querySelector('[class*="piece"] img')
               || document.querySelector('[class*="puzzle"] img');
  const sliderBtn = document.querySelector('.geetest_btn')
                 || document.querySelector('[class*="slider"] button')
                 || document.querySelector('[class*="drag"]');

  if (!bgEl || !sliderBtn) return JSON.stringify({error: 'Captcha elements not found'});

  // 2. Extract pixel data via Canvas
  function getPixels(el) {
    const c = document.createElement('canvas');
    const ctx = c.getContext('2d');
    if (el.tagName === 'CANVAS') {
      c.width = el.width; c.height = el.height;
      ctx.drawImage(el, 0, 0);
    } else {
      c.width = el.naturalWidth || el.width;
      c.height = el.naturalHeight || el.height;
      ctx.drawImage(el, 0, 0, c.width, c.height);
    }
    return ctx.getImageData(0, 0, c.width, c.height);
  }

  // 3. Sobel edge detection (pure JS)
  function sobelEdge(imgData) {
    const {width: w, height: h, data} = imgData;
    const gray = new Float32Array(w * h);
    for (let i = 0; i < w * h; i++)
      gray[i] = 0.299 * data[i*4] + 0.587 * data[i*4+1] + 0.114 * data[i*4+2];
    const edges = new Float32Array(w * h);
    for (let y = 1; y < h-1; y++) {
      for (let x = 1; x < w-1; x++) {
        const gx = -gray[(y-1)*w+x-1] + gray[(y-1)*w+x+1]
                   -2*gray[y*w+x-1] + 2*gray[y*w+x+1]
                   -gray[(y+1)*w+x-1] + gray[(y+1)*w+x+1];
        const gy = -gray[(y-1)*w+x-1] - 2*gray[(y-1)*w+x] - gray[(y-1)*w+x+1]
                   +gray[(y+1)*w+x-1] + 2*gray[(y+1)*w+x] + gray[(y+1)*w+x+1];
        edges[y*w+x] = Math.sqrt(gx*gx + gy*gy);
      }
    }
    return {data: edges, width: w, height: h};
  }

  // 4. NCC template matching
  function nccMatch(bg, tpl) {
    let bestX = 0, bestScore = -1;
    const searchW = bg.width - tpl.width;
    const searchH = bg.height - tpl.height;
    // Pre-compute template stats
    let tMean = 0, tLen = tpl.width * tpl.height;
    for (let i = 0; i < tLen; i++) tMean += tpl.data[i];
    tMean /= tLen;
    let tStd = 0;
    for (let i = 0; i < tLen; i++) tStd += (tpl.data[i] - tMean) ** 2;
    tStd = Math.sqrt(tStd);
    if (tStd < 1) return 0;

    for (let sx = 0; sx < searchW; sx += 2) { // step=2 for speed
      for (let sy = 0; sy < searchH; sy += 2) {
        let bMean = 0;
        for (let ty = 0; ty < tpl.height; ty++)
          for (let tx = 0; tx < tpl.width; tx++)
            bMean += bg.data[(sy+ty)*bg.width + sx+tx];
        bMean /= tLen;
        let bStd = 0, cross = 0;
        for (let ty = 0; ty < tpl.height; ty++) {
          for (let tx = 0; tx < tpl.width; tx++) {
            const bv = bg.data[(sy+ty)*bg.width + sx+tx] - bMean;
            const tv = tpl.data[ty*tpl.width + tx] - tMean;
            cross += bv * tv;
            bStd += bv * bv;
          }
        }
        bStd = Math.sqrt(bStd);
        if (bStd < 1) continue;
        const score = cross / (bStd * tStd);
        if (score > bestScore) { bestScore = score; bestX = sx; }
      }
    }
    return bestX;
  }

  // 5. Run analysis
  const bgData = getPixels(bgEl);
  const bgEdges = sobelEdge(bgData);

  let gapX;
  if (pieceEl) {
    const pcData = getPixels(pieceEl);
    const pcEdges = sobelEdge(pcData);
    gapX = nccMatch(bgEdges, pcEdges);
  } else {
    // Fallback: look for dark rectangular gap in background
    gapX = 0; // Would need contour analysis - use Python fallback
  }

  // 6. Calculate drag coordinates
  const btnRect = sliderBtn.getBoundingClientRect();
  const startX = btnRect.x + btnRect.width / 2;
  const startY = btnRect.y + btnRect.height / 2;

  // Scale: captcha canvas size vs display size
  const bgRect = bgEl.getBoundingClientRect();
  const scale = bgRect.width / bgData.width;
  const distance = Math.round(gapX * scale);

  return JSON.stringify({startX, startY, distance, gapX, scale, confidence: 'ncc'});
})()
```

**Step 2** — Parse the result and immediately execute Chrome MCP `left_click_drag`:

```
start: (startX, startY)
end:   (startX + distance, startY)
```

If simple linear drag is rejected (GeeTest advanced behavior detection), retry with small Y offset or add slight overshoot.

### Approach 2: Screenshot + Python OpenCV (Fallback)

Use when browser Canvas is tainted by CORS or captcha loads in a cross-origin iframe.

```bash
cd ~/.claude/skills/slider-captcha-solver/lib
python solve.py --screenshot /tmp/captcha.png --debug
```

Or from Python:

```python
import sys
sys.path.insert(0, str(Path("~/.claude/skills/slider-captcha-solver/lib").expanduser()))
from solve import solve_from_images, solve_with_playwright

# From images
result = solve_from_images("bg.png", "piece.png", debug=True)
print(f"Drag distance: {result['distance']}px")

# With Playwright page
result = solve_with_playwright(page)  # auto-detects slider, drags with Bezier trajectory
```

Requires: `pip install opencv-python-headless numpy`

## Supported CAPTCHA Types

- GeeTest v3/v4 (slide)
- AliCaptcha / Captcha4 (slide)
- DataDome slider
- TikTok puzzle
- Any generic slider where you drag a piece to fill a gap

## Common Selectors by CAPTCHA Type

| Type | Background | Piece | Slider Button |
|------|-----------|-------|--------------|
| GeeTest v4 | `.geetest_bg` | `.geetest_slice_bg` | `.geetest_btn` |
| GeeTest v3 | `.geetest_canvas_bg canvas` | `.geetest_canvas_slice canvas` | `.geetest_slider_button` |
| AliCaptcha | `#alicaptcha-bg` | `#alicaptcha-slice` | `.alicaptcha-slider` |

## Decision Tree

```
Captcha detected
  |
  +-- Can access DOM images? (no CORS taint)
  |     YES --> Approach 1: In-Browser JS (fast, no dependencies)
  |     NO  --> Approach 2: Screenshot + Python OpenCV
  |
  +-- Simple drag rejected?
        YES --> Add Bezier trajectory (Playwright) or slight Y offset (Chrome MCP)
        NO  --> Done
```

## Troubleshooting

- **Canvas tainted**: CORS blocks `getImageData`. Use Approach 2 (screenshot).
- **Detection fails**: Adjust Sobel blur or try Canny. In Python: `--blur 5` or `--method canny`.
- **Drag rejected**: Captcha detects bot-like movement. Use Playwright with `solve_with_playwright()` for Bezier curve trajectory.
- **Wrong distance**: Check if captcha canvas size differs from display size. The JS approach auto-scales via `bgRect.width / bgData.width`.
