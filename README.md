# AI Skills

A collection of AI agent skills for browser automation, web scraping, and other tasks.

## Skills

### slider-captcha-solver

Solve slider/puzzle CAPTCHA challenges using computer vision gap detection and human-like mouse trajectory simulation.

**Supported CAPTCHA types:** GeeTest v3/v4, AliCaptcha, DataDome, TikTok, and any generic slider CAPTCHA.

**How it works:**

```
Captcha image → Edge Detection (Sobel/Canny) → Template Matching (NCC) → Gap position (px)
                                                                              ↓
                                                            Bezier trajectory generation
                                                                              ↓
                                                              Browser drag execution
```

1. **Gap Detection** (`lib/gap_detector.py`) — Uses OpenCV's Sobel/Canny edge detection on both the background and puzzle piece images, then applies Normalized Cross-Correlation (NCC) template matching to locate the exact gap position. Fallback mode uses adaptive thresholding + contour analysis for single-screenshot scenarios.

2. **Trajectory Generation** (`lib/trajectory.py`) — Generates human-like drag paths using cubic Bezier curves with ease-in-out timing, Gaussian micro-jitter (simulating hand tremor), and optional overshoot-then-correct behavior to bypass bot detection.

3. **Solver** (`lib/solve.py`) — Orchestrates the full pipeline. Supports two modes:
   - **In-browser JS** (preferred) — Runs Sobel + NCC directly in the browser via Canvas API, zero delay between analysis and drag
   - **Python + OpenCV** (fallback) — Screenshot-based, for CORS-restricted iframes

**References:**

- [opencv-python](https://github.com/opencv/opencv-python) — Computer vision library for edge detection and template matching
- [GeeTest crack research](https://github.com/nickliqian/cnnc_captcha) — Inspiration for NCC-based gap detection approach
- Bezier curve trajectory technique adapted from various CAPTCHA solving research papers on human-like mouse movement simulation

## Directory Structure

```
ai-skills/
├── README.md
├── .gitignore
└── slider-captcha-solver/
    ├── SKILL.md              # Skill definition and usage guide
    └── lib/
        ├── __init__.py       # Package exports
        ├── gap_detector.py   # OpenCV gap detection (Sobel/Canny + NCC template matching)
        ├── trajectory.py     # Human-like Bezier curve mouse trajectory generator
        └── solve.py          # Main solver: CLI + Playwright integration
```

## Requirements

- Python 3.10+
- `opencv-python-headless` and `numpy` (for Python/OpenCV mode)
- Playwright or Chrome MCP (for browser automation)

## License

MIT
