import base64
import io
import os
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from config import Config

Image.MAX_IMAGE_PIXELS = Config.MAX_IMAGE_PIXELS

ALLOWED_PILLOW_FORMATS = {"PNG", "JPEG", "WEBP"}


def validate_and_inspect_image(file_bytes: bytes, filename: str = "") -> dict:
    """Validate raw image bytes, check format and dimensions, and return metadata."""
    if not file_bytes:
        raise ValueError("Empty image file.")
    if len(file_bytes) > Config.MAX_CONTENT_LENGTH:
        raise ValueError("File exceeds maximum allowed upload size.")

    try:
        with Image.open(io.BytesIO(file_bytes)) as probe:
            fmt = (probe.format or "").upper()
            if fmt not in ALLOWED_PILLOW_FORMATS:
                raise ValueError(
                    f"Unsupported image format '{fmt or 'unknown'}'. Allowed: PNG, JPG, JPEG, WebP."
                )
            probe.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        if isinstance(exc, ValueError) and "Unsupported image format" in str(exc):
            raise
        raise ValueError("Corrupted or invalid image file.") from exc

    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            img.load()
            width, height = img.size
            max_w, max_h = Config.MAX_IMAGE_DIMENSIONS
            if width < 8 or height < 8:
                raise ValueError("Image dimensions are too small (minimum 8x8 px).")
            if width > max_w or height > max_h:
                raise ValueError(
                    f"Image dimensions ({width}x{height}) exceed maximum ({max_w}x{max_h})."
                )
            has_alpha = _detect_transparency(img)
            return {
                "width": width,
                "height": height,
                "format": fmt,
                "mode": img.mode,
                "has_alpha": has_alpha,
                "size_bytes": len(file_bytes),
            }
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Unable to decode image data.") from exc


def _detect_transparency(img: Image.Image) -> bool:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        alpha_extrema = rgba.getchannel("A").getextrema()
        if alpha_extrema and alpha_extrema[0] < 245:
            return True
    return False


def generate_builtin_image(builtin_id: str, width: int = 900, height: int = 1125) -> Image.Image:
    """Create a procedural editorial silhouette image using Pillow."""
    w = max(200, min(1600, int(width)))
    h = max(200, min(1600, int(height)))
    img = Image.new("RGBA", (w, h), (245, 243, 239, 0))
    draw = ImageDraw.Draw(img)
    fg = (23, 23, 23, 255)

    if builtin_id == "builtin:circle":
        r = int(min(w, h) * 0.39)
        cx, cy = w // 2, h // 2
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fg)

    elif builtin_id == "builtin:arch":
        margin_x = int(w * 0.16)
        top_y = int(h * 0.10)
        bot_y = int(h * 0.90)
        arch_w = w - 2 * margin_x
        radius = arch_w // 2
        cx = w // 2
        cy = top_y + radius
        draw.ellipse((cx - radius, top_y, cx + radius, top_y + 2 * radius), fill=fg)
        draw.rectangle((margin_x, cy, w - margin_x, bot_y), fill=fg)

    elif builtin_id == "builtin:monolith":
        # Stepped brutalist architectural totem
        cx = w // 2
        draw.rectangle((int(w * 0.28), int(h * 0.09), int(w * 0.72), int(h * 0.32)), fill=fg)
        draw.rectangle((int(w * 0.18), int(h * 0.30), int(w * 0.82), int(h * 0.62)), fill=fg)
        draw.rectangle((int(w * 0.12), int(h * 0.60), int(w * 0.88), int(h * 0.91)), fill=fg)
        # Cutout window
        draw.rectangle((cx - int(w * 0.10), int(h * 0.40), cx + int(w * 0.10), int(h * 0.52)), fill=(245, 243, 239, 0))

    elif builtin_id == "builtin:diamond":
        cx, cy = w // 2, h // 2
        rx, ry = int(w * 0.42), int(h * 0.42)
        draw.polygon([(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)], fill=fg)

    else:
        # builtin:portrait — sculptural classical head & shoulders bust silhouette
        cx = w // 2
        # Cranium
        head_rx = int(w * 0.21)
        head_ry = int(h * 0.19)
        head_cy = int(h * 0.30)
        draw.ellipse(
            (cx - head_rx, head_cy - head_ry, cx + head_rx, head_cy + head_ry),
            fill=fg,
        )
        # Jaw & facial contour
        jaw_pts = [
            (cx - int(w * 0.19), head_cy),
            (cx + int(w * 0.19), head_cy),
            (cx + int(w * 0.15), int(h * 0.47)),
            (cx + int(w * 0.06), int(h * 0.53)),
            (cx - int(w * 0.06), int(h * 0.53)),
            (cx - int(w * 0.15), int(h * 0.47)),
        ]
        draw.polygon(jaw_pts, fill=fg)
        # Neck column
        neck_w = int(w * 0.11)
        draw.rectangle(
            (cx - neck_w, int(h * 0.48), cx + neck_w, int(h * 0.63)),
            fill=fg,
        )
        # Sculptural shoulders & torso bust
        bust_pts = [
            (cx - neck_w, int(h * 0.58)),
            (cx + neck_w, int(h * 0.58)),
            (cx + int(w * 0.41), int(h * 0.68)),
            (cx + int(w * 0.43), int(h * 0.91)),
            (cx - int(w * 0.43), int(h * 0.91)),
            (cx - int(w * 0.41), int(h * 0.68)),
        ]
        draw.polygon(bust_pts, fill=fg)
        # Shoulder rounding ellipses
        sr = int(w * 0.09)
        draw.ellipse(
            (cx - int(w * 0.43), int(h * 0.64), cx - int(w * 0.43) + 2 * sr, int(h * 0.64) + 2 * sr),
            fill=fg,
        )
        draw.ellipse(
            (cx + int(w * 0.43) - 2 * sr, int(h * 0.64), cx + int(w * 0.43), int(h * 0.64) + 2 * sr),
            fill=fg,
        )

    return img


def load_normalized_image(file_path: str = None, builtin_id: str = "builtin:portrait", target_size=(900, 1125)) -> Image.Image:
    """Load an uploaded image or generate a built-in silhouette and normalize to RGBA."""
    if file_path and os.path.isfile(file_path):
        with Image.open(file_path) as raw:
            transposed = ImageOps.exif_transpose(raw)
            return transposed.convert("RGBA")
    return generate_builtin_image(builtin_id or "builtin:portrait", target_size[0], target_size[1])


def transform_image_to_canvas(img: Image.Image, settings: dict, working_size: tuple = None) -> Image.Image:
    """Apply crop, fit/fill/stretch mode, scale, and offset onto a target canvas."""
    cw = int(working_size[0]) if working_size else int(settings.get("canvas_width", 900))
    ch = int(working_size[1]) if working_size else int(settings.get("canvas_height", 1125))
    cw = max(64, cw)
    ch = max(64, ch)

    src = img.convert("RGBA")
    sw, sh = src.size

    # Apply source percentage crop
    cl = float(settings.get("crop_left", 0.0)) / 100.0
    ct = float(settings.get("crop_top", 0.0)) / 100.0
    cr = float(settings.get("crop_right", 0.0)) / 100.0
    cb = float(settings.get("crop_bottom", 0.0)) / 100.0

    x0 = int(round(sw * max(0.0, min(0.45, cl))))
    y0 = int(round(sh * max(0.0, min(0.45, ct))))
    x1 = int(round(sw * (1.0 - max(0.0, min(0.45, cr)))))
    y1 = int(round(sh * (1.0 - max(0.0, min(0.45, cb)))))
    if x1 - x0 >= 8 and y1 - y0 >= 8 and (x0 > 0 or y0 > 0 or x1 < sw or y1 < sh):
        src = src.crop((x0, y0, x1, y1))
        sw, sh = src.size

    fit_mode = settings.get("fit_mode", "fit")
    user_scale = float(settings.get("image_scale", 1.0))

    if fit_mode == "stretch":
        new_w = max(8, int(round(cw * user_scale)))
        new_h = max(8, int(round(ch * user_scale)))
    elif fit_mode in ("fill", "crop"):
        base_scale = max(cw / max(1, sw), ch / max(1, sh))
        if fit_mode == "crop":
            base_scale *= 1.08
        scale = base_scale * user_scale
        new_w = max(8, int(round(sw * scale)))
        new_h = max(8, int(round(sh * scale)))
    else:
        # "fit" — preserve aspect ratio inside canvas
        base_scale = min(cw / max(1, sw), ch / max(1, sh))
        scale = base_scale * user_scale
        new_w = max(8, int(round(sw * scale)))
        new_h = max(8, int(round(sh * scale)))

    resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)

    offset_x_pct = float(settings.get("image_offset_x", 0.0)) / 100.0
    offset_y_pct = float(settings.get("image_offset_y", 0.0)) / 100.0

    paste_x = int(round((cw - new_w) / 2.0 + offset_x_pct * cw * 0.5))
    paste_y = int(round((ch - new_h) / 2.0 + offset_y_pct * ch * 0.5))

    # Determine background color for out-of-bounds areas based on image corners or transparency
    has_alpha = _detect_transparency(src)
    if has_alpha:
        bg_rgba = (255, 255, 255, 0)
    else:
        corners = [
            src.getpixel((0, 0)),
            src.getpixel((sw - 1, 0)),
            src.getpixel((0, sh - 1)),
            src.getpixel((sw - 1, sh - 1)),
        ]
        avg_r = sum(c[0] for c in corners) // 4
        avg_g = sum(c[1] for c in corners) // 4
        avg_b = sum(c[2] for c in corners) // 4
        bg_rgba = (avg_r, avg_g, avg_b, 255)

    canvas_img = Image.new("RGBA", (cw, ch), bg_rgba)
    canvas_img.paste(resized, (paste_x, paste_y), resized if has_alpha else None)
    return canvas_img


def image_to_data_url(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{b64}"
