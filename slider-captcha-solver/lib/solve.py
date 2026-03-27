"""
Main solver for slider CAPTCHAs.

Integrates gap detection + trajectory generation + browser drag execution.
Supports Chrome MCP browser and Playwright.

Usage from CLI:
    python solve.py --screenshot /tmp/captcha.png
    python solve.py --background bg.png --piece piece.png

Usage from Python:
    from solve import solve_slider_captcha
    result = solve_slider_captcha(page, mode="playwright")
"""

import argparse
import json
import os
import sys
import time
import tempfile
from pathlib import Path

# Ensure lib directory is in path
LIB_DIR = Path(__file__).parent
sys.path.insert(0, str(LIB_DIR))

from gap_detector import find_gap_distance, find_gap_from_single_image
from trajectory import generate_trajectory


def solve_with_playwright(page, slider_selector: str = None, max_attempts: int = 3, debug: bool = False) -> dict:
    """
    Solve a slider captcha visible on a Playwright page.

    Args:
        page: Playwright page object
        slider_selector: CSS selector for the drag button. Auto-detected if None.
        max_attempts: Max retry attempts
        debug: Save debug images

    Returns:
        {"success": bool, "distance": int, "attempts": int}
    """
    for attempt in range(1, max_attempts + 1):
        try:
            # Auto-detect slider elements
            if not slider_selector:
                for sel in [
                    '.geetest_slider_button',
                    '.captcha-slider-btn',
                    '[class*="slider"] button',
                    '[class*="slider"] [class*="btn"]',
                    '[class*="drag"]',
                    'button[class*="arrow"]',
                ]:
                    if page.query_selector(sel):
                        slider_selector = sel
                        break

            if not slider_selector:
                return {"success": False, "error": "Could not find slider button", "attempts": attempt}

            # Screenshot the captcha area
            captcha_area = page.query_selector('.geetest_widget') or \
                           page.query_selector('[class*="captcha"]') or \
                           page.query_selector('[class*="slider-container"]')

            tmp_dir = tempfile.mkdtemp()

            if captcha_area:
                bg_path = os.path.join(tmp_dir, "captcha_bg.png")
                captcha_area.screenshot(path=bg_path)
            else:
                bg_path = os.path.join(tmp_dir, "captcha_full.png")
                page.screenshot(path=bg_path)

            # Try to get separate piece image
            piece_el = page.query_selector('.geetest_slice') or \
                       page.query_selector('[class*="piece"]') or \
                       page.query_selector('[class*="puzzle"]')

            if piece_el:
                piece_path = os.path.join(tmp_dir, "piece.png")
                piece_el.screenshot(path=piece_path)
                debug_path = os.path.join(tmp_dir, "debug.png") if debug else None
                distance = find_gap_distance(bg_path, piece_path, debug_path=debug_path)
            else:
                debug_path = os.path.join(tmp_dir, "debug.png") if debug else None
                distance = find_gap_from_single_image(bg_path, debug_path=debug_path)

            # Generate trajectory
            slider = page.query_selector(slider_selector)
            box = slider.bounding_box()
            if not box:
                return {"success": False, "error": "Slider button not visible", "attempts": attempt}

            start_x = box["x"] + box["width"] / 2
            start_y = box["y"] + box["height"] / 2

            trajectory = generate_trajectory(distance, int(start_x), int(start_y))

            # Execute drag
            page.mouse.move(int(start_x), int(start_y))
            time.sleep(0.1)
            page.mouse.down()
            time.sleep(0.05)

            for x, y, delay_ms in trajectory:
                page.mouse.move(x, y)
                time.sleep(delay_ms / 1000.0)

            page.mouse.up()
            time.sleep(1.5)

            # Check if solved (captcha disappeared or success indicator)
            still_visible = page.query_selector(slider_selector)
            if not still_visible or not still_visible.is_visible():
                return {"success": True, "distance": distance, "attempts": attempt}

            # Check for success text
            success = page.query_selector('.geetest_success') or \
                      page.query_selector('[class*="success"]')
            if success:
                return {"success": True, "distance": distance, "attempts": attempt}

            time.sleep(1)

        except Exception as e:
            if attempt == max_attempts:
                return {"success": False, "error": str(e), "attempts": attempt}
            time.sleep(2)

    return {"success": False, "error": "Max attempts reached", "attempts": max_attempts}


def solve_from_images(background_path: str, piece_path: str = None, debug: bool = False) -> dict:
    """
    Solve captcha from image files. Returns distance and trajectory.

    Args:
        background_path: Path to background/screenshot image
        piece_path: Path to puzzle piece image (optional)
        debug: Save debug visualization

    Returns:
        {"distance": int, "trajectory": list}
    """
    debug_path = background_path.replace(".png", "_debug.png") if debug else None

    if piece_path:
        distance = find_gap_distance(background_path, piece_path, debug_path=debug_path)
    else:
        distance = find_gap_from_single_image(background_path, debug_path=debug_path)

    trajectory = generate_trajectory(distance)

    return {
        "distance": distance,
        "trajectory": [(x, y, d) for x, y, d in trajectory],
        "debug_path": debug_path,
    }


def main():
    parser = argparse.ArgumentParser(description="Slider CAPTCHA Solver")
    parser.add_argument("--background", "-b", help="Background image path")
    parser.add_argument("--piece", "-p", help="Puzzle piece image path")
    parser.add_argument("--screenshot", "-s", help="Single captcha screenshot")
    parser.add_argument("--debug", action="store_true", help="Save debug images")
    parser.add_argument("--method", default="sobel", choices=["sobel", "canny"])
    args = parser.parse_args()

    if args.screenshot:
        result = solve_from_images(args.screenshot, debug=args.debug)
    elif args.background:
        result = solve_from_images(args.background, args.piece, debug=args.debug)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps({"distance": result["distance"]}, indent=2))
    if result.get("debug_path"):
        print(f"Debug image saved to: {result['debug_path']}")


if __name__ == "__main__":
    main()
