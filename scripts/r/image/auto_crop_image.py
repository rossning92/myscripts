import argparse
import os
import tempfile
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps, JpegImagePlugin


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _to_rgb_array(image: Image.Image) -> np.ndarray:
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        bg = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(bg, image.convert("RGBA")).convert("RGB")
    else:
        image = image.convert("RGB")
    return np.asarray(image)


def _odd_kernel(size: int) -> int:
    size = max(3, int(size))
    return size if size % 2 else size + 1


def _border_samples(lab: np.ndarray, width: int) -> np.ndarray:
    top = lab[:width, :, :].reshape(-1, 3)
    bottom = lab[-width:, :, :].reshape(-1, 3)
    left = lab[:, :width, :].reshape(-1, 3)
    right = lab[:, -width:, :].reshape(-1, 3)
    return np.concatenate([top, bottom, left, right], axis=0)


def _largest_component_bbox(mask: np.ndarray, min_area: int) -> Optional[Tuple[int, int, int, int]]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return None

    candidates = []
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if area >= min_area:
            candidates.append((area, x, y, w, h))

    if not candidates:
        return None

    _, x, y, w, h = max(candidates)
    return x, y, x + w, y + h


def _projection_bbox(mask: np.ndarray, row_ratio: float, col_ratio: float) -> Optional[Tuple[int, int, int, int]]:
    h, w = mask.shape
    rows = np.count_nonzero(mask, axis=1) >= max(1, int(w * row_ratio))
    cols = np.count_nonzero(mask, axis=0) >= max(1, int(h * col_ratio))

    if not rows.any() or not cols.any():
        return None

    y1, y2 = np.flatnonzero(rows)[[0, -1]]
    x1, x2 = np.flatnonzero(cols)[[0, -1]]
    return int(x1), int(y1), int(x2 + 1), int(y2 + 1)


def _union_bbox(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def find_crop_box(
    image: Image.Image,
    threshold: Optional[float] = None,
    border_width_ratio: float = 0.02,
    min_crop_ratio: float = 0.01,
) -> Tuple[int, int, int, int]:
    rgb = _to_rgb_array(image)
    h, w = rgb.shape[:2]
    if h < 2 or w < 2:
        return 0, 0, w, h

    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    border_width = max(2, min(w, h) // 100, int(min(w, h) * border_width_ratio))
    border_width = min(border_width, max(1, min(w, h) // 4))
    samples = _border_samples(lab, border_width)
    border_color = np.median(samples, axis=0)
    dist = np.linalg.norm(lab - border_color, axis=2)
    border_dist = np.linalg.norm(samples - border_color, axis=1)

    if threshold is None:
        median = float(np.median(border_dist))
        inlier_limit = float(np.percentile(border_dist, 75))
        inliers = border_dist[border_dist <= inlier_limit]
        if inliers.size < max(16, border_dist.size // 10):
            inlier_limit = float(np.percentile(border_dist, 90))
            inliers = border_dist[border_dist <= inlier_limit]
        if inliers.size == 0:
            inliers = border_dist
        inlier_median = float(np.median(inliers))
        inlier_mad = float(np.median(np.abs(inliers - inlier_median)))
        threshold = max(
            12.0,
            median + 6.0 * max(inlier_mad, 1.0),
            float(np.percentile(inliers, 95)) + 5.0,
        )

    mask = (dist > threshold).astype(np.uint8) * 255

    small_kernel_size = _odd_kernel(max(3, min(w, h) // 250))
    large_kernel_size = _odd_kernel(max(5, min(w, h) // 80))
    small_kernel = np.ones((small_kernel_size, small_kernel_size), np.uint8)
    large_kernel = np.ones((large_kernel_size, large_kernel_size), np.uint8)

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, small_kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, large_kernel)
    mask = cv2.dilate(mask, small_kernel, iterations=1)

    min_area = max(16, int(w * h * 0.001))
    component_box = _largest_component_bbox(mask, min_area)
    projection_box = _projection_bbox(mask, row_ratio=0.005, col_ratio=0.005)

    if component_box is None and projection_box is None:
        return 0, 0, w, h
    if component_box is None:
        box = projection_box
    elif projection_box is None:
        box = component_box
    else:
        box = _union_bbox(component_box, projection_box)

    x1, y1, x2, y2 = box

    if x2 <= x1 or y2 <= y1:
        return 0, 0, w, h

    cropped_area = (x2 - x1) * (y2 - y1)
    if cropped_area < w * h * min_crop_ratio:
        return 0, 0, w, h

    return x1, y1, x2, y2


def _jpeg_save_kwargs(original: Image.Image) -> dict:
    save_kwargs = {}
    if getattr(original, "format", None) == "JPEG":
        if getattr(original, "quantization", None):
            save_kwargs["qtables"] = original.quantization
        try:
            save_kwargs["subsampling"] = JpegImagePlugin.get_sampling(original)
        except Exception:
            pass
        if "icc_profile" in original.info:
            save_kwargs["icc_profile"] = original.info["icc_profile"]
    else:
        save_kwargs.update(quality=95, subsampling=0)
    return save_kwargs


def auto_crop_image(
    input_file: str,
    output_file: str,
    threshold: Optional[float] = None,
    border_width_ratio: float = 0.02,
) -> Tuple[int, int, int, int]:
    with Image.open(input_file) as original:
        image = ImageOps.exif_transpose(original)
        box = find_crop_box(
            image,
            threshold=threshold,
            border_width_ratio=border_width_ratio,
        )
        cropped = image.crop(box)

        save_kwargs = {}
        ext = os.path.splitext(output_file)[1].lower()
        if ext in {".jpg", ".jpeg"}:
            if cropped.mode in ("RGBA", "LA", "P"):
                cropped = cropped.convert("RGB")
            save_kwargs.update(_jpeg_save_kwargs(original))

        cropped.save(output_file, **save_kwargs)
        return box


def _output_path(input_file: str, output: Optional[str], inplace: bool) -> str:
    if inplace:
        return input_file
    if output:
        return output
    base, ext = os.path.splitext(input_file)
    return f"{base}_cropped{ext}"


def _save_inplace(input_file: str, threshold: Optional[float], border_width_ratio: float) -> Tuple[int, int, int, int]:
    directory = os.path.dirname(os.path.abspath(input_file)) or "."
    fd, temp_file = tempfile.mkstemp(suffix=os.path.splitext(input_file)[1], dir=directory)
    os.close(fd)
    try:
        box = auto_crop_image(input_file, temp_file, threshold, border_width_ratio)
        os.replace(temp_file, input_file)
        return box
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Automatically crop noisy image borders from PNG/JPEG scans.")
    parser.add_argument("input", help="Input PNG or JPEG image")
    parser.add_argument("output", nargs="?", help="Output image path. Defaults to INPUT_cropped.ext")
    parser.add_argument("--inplace", action="store_true", help="Overwrite the input image")
    parser.add_argument("--threshold", type=float, help="Manual border distance threshold in Lab color space")
    parser.add_argument("--border-width-ratio", type=float, default=0.02, help="Outer image ratio used to estimate border color")
    args = parser.parse_args()

    ext = os.path.splitext(args.input)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        raise SystemExit("Input must be a PNG or JPEG image")

    if args.inplace and args.output:
        raise SystemExit("Do not pass output when using --inplace")

    if args.inplace:
        box = _save_inplace(args.input, args.threshold, args.border_width_ratio)
        out_file = args.input
    else:
        out_file = _output_path(args.input, args.output, args.inplace)
        box = auto_crop_image(args.input, out_file, args.threshold, args.border_width_ratio)

    print(f"crop box: {box[0]} {box[1]} {box[2]} {box[3]}")
    print(f"output: {out_file}")


if __name__ == "__main__":
    main()
