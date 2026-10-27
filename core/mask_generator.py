from collections import OrderedDict
import hashlib
import json
import numpy as np
from PIL import Image, ImageEnhance
from config import Config
from core.image_processor import (
    _detect_transparency,
    image_to_data_url,
    load_normalized_image,
    transform_image_to_canvas,
)

_MASK_CACHE = OrderedDict()
_MAX_CACHE_ENTRIES = 24


class MaskData:
    """Normalized binary mask and integral summed-area table for O(1) overlap queries."""

    def __init__(
        self,
        binary_mask: np.ndarray,
        canvas_width: int,
        canvas_height: int,
        coverage_ratio: float,
        used_alpha: bool = False,
    ):
        self.binary = binary_mask.astype(np.uint8)
        self.mask_h, self.mask_w = self.binary.shape
        self.canvas_width = int(canvas_width)
        self.canvas_height = int(canvas_height)
        self.coverage_ratio = float(coverage_ratio)
        self.used_alpha = bool(used_alpha)
        # Padded integral image: shape (mask_h + 1, mask_w + 1)
        self.integral = np.zeros((self.mask_h + 1, self.mask_w + 1), dtype=np.int64)
        np.cumsum(np.cumsum(self.binary, axis=0), axis=1, out=self.integral[1:, 1:])

    def box_overlap_ratio(self, x: float, y: float, w: float, h: float) -> float:
        """Return fraction [0.0, 1.0] of rectangle (x, y, w, h) in canvas coords that lies inside mask."""
        if w <= 0 or h <= 0:
            return 0.0
        scale_x = self.mask_w / max(1.0, float(self.canvas_width))
        scale_y = self.mask_h / max(1.0, float(self.canvas_height))

        ix0 = max(0, min(self.mask_w, int(round(x * scale_x))))
        iy0 = max(0, min(self.mask_h, int(round(y * scale_y))))
        ix1 = max(0, min(self.mask_w, int(round((x + w) * scale_x))))
        iy1 = max(0, min(self.mask_h, int(round((y + h) * scale_y))))

        if ix1 <= ix0 or iy1 <= iy0:
            return 0.0

        area = (ix1 - ix0) * (iy1 - iy0)
        active = (
            self.integral[iy1, ix1]
            - self.integral[iy0, ix1]
            - self.integral[iy1, ix0]
            + self.integral[iy0, ix0]
        )
        return float(active) / float(area)

    def row_active_spans(self, y: float, h: float, min_density: float = 0.25):
        """Return list of (x_start, x_end) spans in canvas coordinates where the row band has mask presence."""
        scale_x = self.mask_w / max(1.0, float(self.canvas_width))
        scale_y = self.mask_h / max(1.0, float(self.canvas_height))

        iy0 = max(0, min(self.mask_h - 1, int(round(y * scale_y))))
        iy1 = max(iy0 + 1, min(self.mask_h, int(round((y + h) * scale_y))))
        band_h = iy1 - iy0

        col_sums = self.integral[iy1, 1:] - self.integral[iy0, 1:] - (
            self.integral[iy1, :-1] - self.integral[iy0, :-1]
        )
        active_cols = col_sums >= max(1, int(band_h * min_density))
        if not np.any(active_cols):
            return []

        padded = np.concatenate(([False], active_cols, [False]))
        starts = np.where(padded[1:] & ~padded[:-1])[0]
        ends = np.where(~padded[1:] & padded[:-1])[0]

        inv_scale_x = float(self.canvas_width) / max(1.0, float(self.mask_w))
        spans = []
        for s, e in zip(starts, ends):
            spans.append((s * inv_scale_x, e * inv_scale_x))
        return spans


def _compute_working_dimensions(canvas_w: int, canvas_h: int) -> tuple:
    max_dim = Config.WORKING_MASK_MAX_DIM
    if max(canvas_w, canvas_h) <= max_dim:
        return int(canvas_w), int(canvas_h)
    scale = max_dim / float(max(canvas_w, canvas_h))
    return max(64, int(round(canvas_w * scale))), max(64, int(round(canvas_h * scale)))


def _make_cache_key(file_path: str, settings: dict) -> str:
    mtime = 0.0
    if file_path:
        try:
            mtime = round(float(os.path.getmtime(file_path)), 3)
        except OSError:
            mtime = 0.0
    relevant = {
        "file_path": file_path or "",
        "mtime": mtime,
        "image_id": settings.get("image_id", "builtin:portrait"),
        "canvas_width": settings.get("canvas_width", 900),
        "canvas_height": settings.get("canvas_height", 1125),
        "fill_mode": settings.get("fill_mode", "silhouette"),
        "fit_mode": settings.get("fit_mode", "fit"),
        "threshold": settings.get("threshold", 128),
        "contrast": settings.get("contrast", 1.2),
        "invert_mask": settings.get("invert_mask", False),
        "fg_mode": settings.get("fg_mode", "auto"),
        "image_scale": settings.get("image_scale", 1.0),
        "image_offset_x": settings.get("image_offset_x", 0.0),
        "image_offset_y": settings.get("image_offset_y", 0.0),
        "crop_left": settings.get("crop_left", 0.0),
        "crop_top": settings.get("crop_top", 0.0),
        "crop_right": settings.get("crop_right", 0.0),
        "crop_bottom": settings.get("crop_bottom", 0.0),
    }
    raw = json.dumps(relevant, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


import os  # Ensure os is available for _make_cache_key


def build_mask(settings: dict, file_path: str = None, use_cache: bool = True) -> MaskData:
    """Generate a normalized binary mask and integral table from image and mask settings."""
    cw = int(settings.get("canvas_width", 900))
    ch = int(settings.get("canvas_height", 1125))
    work_w, work_h = _compute_working_dimensions(cw, ch)

    fill_mode = settings.get("fill_mode", "silhouette")
    image_id = settings.get("image_id", "builtin:portrait")

    if fill_mode == "rectangle" or image_id in ("none", ""):
        ones = np.ones((work_h, work_w), dtype=np.uint8)
        if settings.get("invert_mask", False) and fill_mode != "rectangle":
            ones = 1 - ones
        return MaskData(
            binary_mask=ones,
            canvas_width=cw,
            canvas_height=ch,
            coverage_ratio=float(np.mean(ones)),
            used_alpha=False,
        )

    cache_key = _make_cache_key(file_path, settings)
    if use_cache and cache_key in _MASK_CACHE:
        _MASK_CACHE.move_to_end(cache_key)
        return _MASK_CACHE[cache_key]

    raw_img = load_normalized_image(
        file_path=file_path,
        builtin_id=image_id,
        target_size=(work_w, work_h),
    )
    transformed = transform_image_to_canvas(raw_img, settings, working_size=(work_w, work_h))

    fg_mode = settings.get("fg_mode", "auto")
    threshold = int(settings.get("threshold", 128))
    contrast = float(settings.get("contrast", 1.2))
    invert_mask = bool(settings.get("invert_mask", False))

    has_alpha = _detect_transparency(transformed)
    use_alpha = fg_mode == "alpha" or (fg_mode == "auto" and has_alpha)

    if use_alpha:
        alpha_chan = transformed.getchannel("A")
        if abs(contrast - 1.0) > 0.01:
            alpha_chan = ImageEnhance.Contrast(alpha_chan).enhance(contrast)
        arr = np.asarray(alpha_chan, dtype=np.uint8)
        binary = (arr >= threshold).astype(np.uint8)
    else:
        # Composite onto neutral background if any alpha exists, then convert to grayscale
        rgb_bg = Image.new("RGB", transformed.size, (255, 255, 255))
        rgb_bg.paste(transformed, mask=transformed.getchannel("A"))
        gray = rgb_bg.convert("L")
        if abs(contrast - 1.0) > 0.01:
            gray = ImageEnhance.Contrast(gray).enhance(contrast)
        arr = np.asarray(gray, dtype=np.uint8)

        if fg_mode == "light_on_dark":
            binary = (arr >= threshold).astype(np.uint8)
        elif fg_mode == "dark_on_light":
            binary = (arr <= threshold).astype(np.uint8)
        else:
            # auto: inspect border luminance to decide whether background is light or dark
            top_edge = arr[0, :]
            bot_edge = arr[-1, :]
            left_edge = arr[:, 0]
            right_edge = arr[:, -1]
            border_mean = float(
                np.mean(np.concatenate([top_edge, bot_edge, left_edge, right_edge]))
            )
            if border_mean >= 127.0:
                # Light background -> dark foreground subject
                binary = (arr <= threshold).astype(np.uint8)
            else:
                # Dark background -> light foreground subject
                binary = (arr >= threshold).astype(np.uint8)

    if invert_mask:
        binary = 1 - binary

    coverage = float(np.mean(binary))
    mask_data = MaskData(
        binary_mask=binary,
        canvas_width=cw,
        canvas_height=ch,
        coverage_ratio=coverage,
        used_alpha=use_alpha,
    )

    if use_cache:
        _MASK_CACHE[cache_key] = mask_data
        while len(_MASK_CACHE) > _MAX_CACHE_ENTRIES:
            _MASK_CACHE.popitem(last=False)

    return mask_data


def render_mask_preview(mask_data: MaskData, max_preview_dim: int = 480) -> str:
    """Render binary mask as an editorial two-tone PNG data URL for the UI preview."""
    h, w = mask_data.binary.shape
    scale = min(1.0, max_preview_dim / float(max(w, h)))
    pw = max(32, int(round(w * scale)))
    ph = max(32, int(round(h * scale)))

    # Active region = #171717 (near-black), outside = #F5F3EF (warm off-white)
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    active = mask_data.binary == 1
    rgb[active] = (23, 23, 23)
    rgb[~active] = (245, 243, 239)

    img = Image.fromarray(rgb, mode="RGB")
    if (pw, ph) != (w, h):
        img = img.resize((pw, ph), Image.Resampling.NEAREST)
    return image_to_data_url(img, fmt="PNG")
