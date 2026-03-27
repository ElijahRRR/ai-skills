"""
Gap detector for slider/puzzle CAPTCHAs using OpenCV.

Finds the x-offset where the puzzle piece should be dragged to fill the gap
in the background image.

Techniques:
  - Sobel edge detection (more robust than Canny for varying lighting)
  - Gaussian blur for noise reduction
  - Template matching with normalized cross-correlation (TM_CCOEFF_NORMED)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Union


def _load_image(source: Union[str, Path, bytes, np.ndarray]) -> np.ndarray:
    """Load image from file path, bytes, or numpy array."""
    if isinstance(source, np.ndarray):
        return source
    if isinstance(source, bytes):
        arr = np.frombuffer(source, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return cv2.imread(str(source), cv2.IMREAD_COLOR)


def _sobel_edges(img: np.ndarray, blur_ksize: int = 3) -> np.ndarray:
    """Apply Gaussian blur + Sobel edge detection."""
    blurred = cv2.GaussianBlur(img, (blur_ksize, blur_ksize), 0)
    gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_16S, 0, 1, ksize=3)
    abs_x = cv2.convertScaleAbs(grad_x)
    abs_y = cv2.convertScaleAbs(grad_y)
    return cv2.addWeighted(abs_x, 0.5, abs_y, 0.5, 0)


def _canny_edges(img: np.ndarray, low: int = 100, high: int = 200) -> np.ndarray:
    """Apply Canny edge detection."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Canny(gray, low, high)


def _crop_non_zero(img: np.ndarray, padding: int = 0):
    """Crop image to the bounding box of non-zero pixels. Returns (cropped, x_offset, y_offset)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    coords = cv2.findNonZero(gray)
    if coords is None:
        return img, 0, 0
    x, y, w, h = cv2.boundingRect(coords)
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(img.shape[1] - x, w + 2 * padding)
    h = min(img.shape[0] - y, h + 2 * padding)
    return img[y:y+h, x:x+w], x, y


def find_gap_distance(
    background: Union[str, Path, bytes, np.ndarray],
    piece: Union[str, Path, bytes, np.ndarray],
    method: str = "sobel",
    blur_ksize: int = 3,
    debug_path: str = None,
) -> int:
    """
    Find the horizontal distance to drag the puzzle piece.

    Args:
        background: Background image (with gap/shadow visible)
        piece: Puzzle piece image (the draggable part)
        method: Edge detection method - "sobel" (default, more robust) or "canny"
        blur_ksize: Gaussian blur kernel size (odd number, default 3)
        debug_path: If set, save debug visualization to this path

    Returns:
        Horizontal pixel distance to drag the piece
    """
    bg_img = _load_image(background)
    pc_img = _load_image(piece)

    if bg_img is None or pc_img is None:
        raise ValueError("Failed to load one or both images")

    # Edge detection
    if method == "sobel":
        bg_edges = _sobel_edges(bg_img, blur_ksize)
        pc_edges = _sobel_edges(pc_img, blur_ksize)
    else:
        bg_edges = _canny_edges(bg_img)
        pc_edges = _canny_edges(pc_img)

    # Crop piece to non-zero content (remove transparent/white borders)
    pc_cropped, pc_x_off, pc_y_off = _crop_non_zero(pc_edges, padding=2)

    if pc_cropped.shape[0] > bg_edges.shape[0] or pc_cropped.shape[1] > bg_edges.shape[1]:
        raise ValueError(
            f"Piece ({pc_cropped.shape}) larger than background ({bg_edges.shape}). "
            "Check that images are correct."
        )

    # Template matching
    result = cv2.matchTemplate(bg_edges, pc_cropped, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    gap_x = max_loc[0]

    # Debug visualization
    if debug_path:
        debug_img = bg_img.copy()
        h, w = pc_cropped.shape[:2]
        cv2.rectangle(debug_img, max_loc, (gap_x + w, max_loc[1] + h), (0, 255, 0), 2)
        cv2.putText(debug_img, f"x={gap_x} conf={max_val:.2f}",
                     (gap_x, max_loc[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.imwrite(debug_path, debug_img)

    return gap_x


def find_gap_from_single_image(
    screenshot: Union[str, Path, bytes, np.ndarray],
    method: str = "sobel",
    debug_path: str = None,
) -> int:
    """
    Find gap position from a single screenshot of the captcha.
    Uses edge detection + contour analysis to find the dark gap region.

    This is a fallback for when separate piece/background images aren't available.
    Works by finding the darkest rectangular region that looks like a gap.

    Args:
        screenshot: Full captcha screenshot
        method: Edge detection method
        debug_path: Debug output path

    Returns:
        Estimated x position of the gap
    """
    img = _load_image(screenshot)
    if img is None:
        raise ValueError("Failed to load screenshot")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Find dark regions (gaps are typically darker than surroundings)
    # Use adaptive thresholding
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY_INV, 11, 2)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter: gap-shaped contours (roughly square, reasonable size)
    h_img, w_img = img.shape[:2]
    min_size = min(h_img, w_img) * 0.08
    max_size = min(h_img, w_img) * 0.4
    candidates = []

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = w / h if h > 0 else 0
        if min_size < w < max_size and min_size < h < max_size and 0.5 < aspect < 2.0:
            # Prefer candidates that are darker than surroundings
            roi = gray[y:y+h, x:x+w]
            mean_val = np.mean(roi)
            candidates.append((x, y, w, h, mean_val))

    if not candidates:
        raise ValueError("Could not detect gap in screenshot")

    # Pick the darkest candidate that's not too far left (piece starts on left)
    candidates.sort(key=lambda c: c[4])  # sort by darkness
    # Filter out leftmost 15% (that's usually the piece, not the gap)
    right_candidates = [c for c in candidates if c[0] > w_img * 0.15]
    best = right_candidates[0] if right_candidates else candidates[0]

    gap_x = best[0]

    if debug_path:
        debug_img = img.copy()
        cv2.rectangle(debug_img, (best[0], best[1]),
                       (best[0] + best[2], best[1] + best[3]), (0, 255, 0), 2)
        cv2.imwrite(debug_path, debug_img)

    return gap_x
