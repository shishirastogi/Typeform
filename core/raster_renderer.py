import io
from PIL import Image, ImageDraw
from config import Config
from core.layout_engine import _hex_to_rgb
from core.typography import get_pil_font, measure_text_Cached


def _draw_spaced_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x_left: float,
    y_top: float,
    font,
    letter_spacing_px: float,
    fill_rgba: tuple,
):
    """Draw text with exact character-by-character letter spacing when letter_spacing != 0."""
    if not text:
        return
    if abs(letter_spacing_px) <= 0.05 or len(text) <= 1:
        draw.text((x_left, y_top), text, font=font, fill=fill_rgba)
        return

    cursor_x = float(x_left)
    for ch in text:
        draw.text((cursor_x, y_top), ch, font=font, fill=fill_rgba)
        try:
            adv = float(font.getlength(ch))
        except AttributeError:
            bbox = font.getbbox(ch)
            adv = float(bbox[2] - bbox[0]) if bbox else 8.0
        cursor_x += adv + letter_spacing_px


def render_raster(
    layout: dict,
    fmt: str = "png",
    scale: int = 1,
    transparent: bool = False,
    bg_color: str = None,
    jpg_quality: int = 95,
) -> tuple:
    """
    Render the layout geometry at native scaled resolution (1x, 2x, 3x, 4x) to PNG or JPG bytes.
    Returns (image_bytes, width, height, mime_type).
    """
    fmt_clean = (fmt or "png").lower()
    if fmt_clean in ("jpeg", "jpg"):
        fmt_clean = "jpg"
        transparent = False  # JPEG does not support transparency
    else:
        fmt_clean = "png"

    mult = max(1, min(4, int(scale)))
    base_w = int(layout.get("canvas_width", 900))
    base_h = int(layout.get("canvas_height", 1125))
    out_w = base_w * mult
    out_h = base_h * mult

    if out_w > Config.MAX_EXPORT_DIMENSION or out_h > Config.MAX_EXPORT_DIMENSION:
        raise ValueError(
            f"Requested export dimensions ({out_w}x{out_h}) exceed memory safety limit ({Config.MAX_EXPORT_DIMENSION}px)."
        )

    effective_bg = bg_color or layout.get("background_color", "#F5F3EF")
    bg_rgb = _hex_to_rgb(effective_bg)

    if transparent and fmt_clean == "png":
        img = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    else:
        img = Image.new("RGBA", (out_w, out_h), (*bg_rgb, 255))

    draw = ImageDraw.Draw(img)

    font_family = layout.get("font_family", "Space Grotesk")
    font_weight = str(layout.get("font_weight", "700"))
    font_style = layout.get("font_style", "normal")
    letter_spacing = float(layout.get("letter_spacing", 0.5))
    line_height = float(layout.get("line_height", 1.15))
    padding_x = float(layout.get("padding_x", 6))
    padding_y = float(layout.get("padding_y", 4))

    for box in layout.get("boxes", []):
        bx = float(box["x"]) * mult
        by = float(box["y"]) * mult
        bw = float(box["w"]) * mult
        bh = float(box["h"]) * mult

        fill_hex = box.get("fill", "#171717")
        txt_hex = box.get("text_color", "#F5F3EF")
        border_w = int(box.get("border_width", 0)) * mult
        border_hex = box.get("border_color", "#171717")

        x0 = int(round(bx))
        y0 = int(round(by))
        x1 = max(x0 + 1, int(round(bx + bw)))
        y1 = max(y0 + 1, int(round(by + bh)))

        fill_rgba = (*_hex_to_rgb(fill_hex), 255) if (fill_hex and fill_hex != "none") else None
        outline_rgba = (*_hex_to_rgb(border_hex), 255) if border_w > 0 else None

        if fill_rgba or outline_rgba:
            draw.rectangle(
                [x0, y0, x1 - 1, y1 - 1],
                fill=fill_rgba,
                outline=outline_rgba,
                width=border_w if border_w > 0 else 0,
            )

        lines = box.get("lines") or [box.get("text", "")]
        fsize_base = float(box.get("font_size", 15))
        fsize_scaled = max(4, int(round(fsize_base * mult)))
        ls_scaled = letter_spacing * mult

        font = get_pil_font(font_family, fsize_scaled, font_weight, font_style)
        txt_rgba = (*_hex_to_rgb(txt_hex), 255)

        cap_h_base = float(box.get("cap_h", fsize_base * 0.72))
        cap_h = cap_h_base * mult
        px = padding_x * mult
        py = padding_y * mult

        h_align = box.get("h_align", "center")
        v_align = box.get("v_align", "middle")

        n_lines = len(lines)
        line_step = cap_h * line_height
        total_text_h = cap_h + (n_lines - 1) * line_step

        if v_align == "top":
            first_top_y = by + py
        elif v_align == "bottom":
            first_top_y = by + bh - py - total_text_h
        else:
            first_top_y = by + (bh - total_text_h) * 0.5

        for l_idx, ln in enumerate(lines):
            if not ln:
                continue
            line_w_base, _ = measure_text_Cached(
                ln, font_family, int(round(fsize_base)), font_weight, font_style, letter_spacing
            )
            line_w = line_w_base * mult

            if h_align == "left":
                line_left_x = bx + px
            elif h_align == "right":
                line_left_x = bx + bw - px - line_w
            else:
                line_left_x = bx + (bw - line_w) * 0.5

            # Adjust for FreeType top bearing offset so glyph top aligns with target y
            try:
                bbox = font.getbbox(ln)
                top_bearing = float(bbox[1]) if bbox else 0.0
            except Exception:
                top_bearing = 0.0

            draw_y = first_top_y + l_idx * line_step - top_bearing
            _draw_spaced_text(
                draw,
                ln,
                line_left_x,
                draw_y,
                font,
                ls_scaled,
                txt_rgba,
            )

    buf = io.BytesIO()
    if fmt_clean == "jpg":
        rgb_img = img.convert("RGB")
        quality = max(10, min(100, int(jpg_quality)))
        rgb_img.save(buf, format="JPEG", quality=quality, subsampling=0, optimize=True)
        return (buf.getvalue(), out_w, out_h, "image/jpeg")
    else:
        img.save(buf, format="PNG", optimize=False)
        return (buf.getvalue(), out_w, out_h, "image/png")
