from functools import lru_cache
import html
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from core.typography import measure_text_Cached, resolve_font_path


@lru_cache(maxsize=32)
def _load_ttfont(font_path: str):
    return TTFont(font_path)


@lru_cache(maxsize=4096)
def _get_glyph_outline(font_path: str, char: str) -> tuple:
    """Return (svg_path_commands, advance_width, units_per_em, ascender) for a single character."""
    tt = _load_ttfont(font_path)
    units_per_em = float(tt["head"].unitsPerEm)
    ascender = float(tt["hhea"].ascent)
    cmap = tt.getBestCmap() or {}
    glyph_set = tt.getGlyphSet()

    code = ord(char)
    glyph_name = cmap.get(code) or cmap.get(32) or ".notdef"
    if glyph_name not in glyph_set:
        return ("", units_per_em * 0.5, units_per_em, ascender)

    glyph = glyph_set[glyph_name]
    pen = SVGPathPen(glyph_set)
    glyph.draw(pen)
    return (pen.getCommands(), float(glyph.width), units_per_em, ascender)


def _render_line_as_outlines(
    line_text: str,
    x_left: float,
    y_baseline: float,
    font_path: str,
    font_size_scaled: float,
    letter_spacing_scaled: float,
    text_color: str,
) -> str:
    """Convert a line of text into SVG <path> elements using fontTools."""
    if not line_text:
        return ""
    paths = []
    cursor_x = x_left
    safe_color = html.escape(text_color, quote=True)

    for ch in line_text:
        cmds, adv_w, upm, _ = _get_glyph_outline(font_path, ch)
        scale = font_size_scaled / max(1.0, upm)
        if cmds and not ch.isspace():
            # Font coordinates have Y-axis pointing up; flip Y around baseline
            tx = round(cursor_x, 2)
            ty = round(y_baseline, 2)
            s_fmt = round(scale, 5)
            paths.append(
                f'<path d="{cmds}" fill="{safe_color}" '
                f'transform="translate({tx},{ty}) scale({s_fmt},{-s_fmt})"/>'
            )
        cursor_x += adv_w * scale + letter_spacing_scaled

    return "".join(paths)


def render_svg(
    layout: dict,
    scale: int = 1,
    transparent: bool = False,
    bg_color: str = None,
    outline_text: bool = False,
) -> str:
    """
    Render the layout geometry into a complete, standards-compliant SVG document.
    Scales all dimensions, coordinates, boxes, and typography by `scale` (1x, 2x, 3x, 4x).
    """
    mult = max(1, min(4, int(scale)))
    base_w = int(layout.get("canvas_width", 900))
    base_h = int(layout.get("canvas_height", 1125))
    out_w = base_w * mult
    out_h = base_h * mult

    effective_bg = bg_color or layout.get("background_color", "#F5F3EF")
    safe_bg = html.escape(effective_bg, quote=True)

    font_family = layout.get("font_family", "Space Grotesk")
    font_weight = str(layout.get("font_weight", "700"))
    font_style = layout.get("font_style", "normal")
    letter_spacing = float(layout.get("letter_spacing", 0.5))
    line_height = float(layout.get("line_height", 1.15))
    padding_x = float(layout.get("padding_x", 6))
    padding_y = float(layout.get("padding_y", 4))

    safe_family = html.escape(font_family, quote=True)
    safe_weight = html.escape(font_weight, quote=True)
    safe_style = html.escape(font_style, quote=True)

    font_path = resolve_font_path(font_family, font_weight, font_style)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w}" height="{out_h}" '
        f'viewBox="0 0 {out_w} {out_h}" shape-rendering="geometricPrecision" text-rendering="geometricPrecision">',
        f"<title>TYPEFORM Typography Artwork ({out_w}x{out_h})</title>",
    ]

    if not outline_text:
        parts.append(
            "<defs><style>"
            f".tf-text {{ font-family: '{safe_family}', 'Neue Machina', sans-serif; "
            f"font-weight: {safe_weight}; font-style: {safe_style}; }}"
            "</style></defs>"
        )

    if not transparent:
        parts.append(
            f'<rect id="background" x="0" y="0" width="{out_w}" height="{out_h}" fill="{safe_bg}"/>'
        )

    parts.append('<g id="artwork-boxes">')

    for box in layout.get("boxes", []):
        bx = round(float(box["x"]) * mult, 2)
        by = round(float(box["y"]) * mult, 2)
        bw = round(float(box["w"]) * mult, 2)
        bh = round(float(box["h"]) * mult, 2)

        fill = box.get("fill", "#171717")
        txt_color = box.get("text_color", "#F5F3EF")
        border_w = int(box.get("border_width", 0)) * mult
        border_c = box.get("border_color", "#171717")

        if fill and fill != "none":
            safe_fill = html.escape(fill, quote=True)
            stroke_attr = ""
            if border_w > 0:
                safe_stroke = html.escape(border_c, quote=True)
                stroke_attr = f' stroke="{safe_stroke}" stroke-width="{border_w}"'
            parts.append(
                f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{safe_fill}"{stroke_attr}/>'
            )
        elif border_w > 0:
            safe_stroke = html.escape(border_c, quote=True)
            parts.append(
                f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="none" stroke="{safe_stroke}" stroke-width="{border_w}"/>'
            )

        lines = box.get("lines") or [box.get("text", "")]
        fsize_base = float(box.get("font_size", 15))
        fsize = round(fsize_base * mult, 2)
        ls_scaled = round(letter_spacing * mult, 2)
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
            first_baseline_y = by + py + cap_h
        elif v_align == "bottom":
            first_baseline_y = by + bh - py - (n_lines - 1) * line_step
        else:
            first_baseline_y = by + (bh - total_text_h) * 0.5 + cap_h

        safe_txt_color = html.escape(txt_color, quote=True)

        for l_idx, ln in enumerate(lines):
            if not ln:
                continue
            line_w_base, _ = measure_text_Cached(
                ln, font_family, int(round(fsize_base)), font_weight, font_style, letter_spacing
            )
            line_w = line_w_base * mult
            baseline_y = round(first_baseline_y + l_idx * line_step, 2)

            if h_align == "left":
                line_left_x = bx + px
                anchor = "start"
                anchor_x = round(bx + px, 2)
            elif h_align == "right":
                line_left_x = bx + bw - px - line_w
                anchor = "end"
                anchor_x = round(bx + bw - px, 2)
            else:
                line_left_x = bx + (bw - line_w) * 0.5
                anchor = "middle"
                anchor_x = round(bx + bw * 0.5, 2)

            if outline_text:
                parts.append(
                    _render_line_as_outlines(
                        ln,
                        line_left_x,
                        baseline_y,
                        font_path,
                        fsize,
                        ls_scaled,
                        txt_color,
                    )
                )
            else:
                escaped_ln = html.escape(ln, quote=False)
                ls_attr = f' letter-spacing="{ls_scaled}px"' if abs(ls_scaled) > 0.01 else ""
                parts.append(
                    f'<text class="tf-text" x="{anchor_x}" y="{baseline_y}" '
                    f'text-anchor="{anchor}" font-size="{fsize}px" fill="{safe_txt_color}"{ls_attr}>'
                    f"{escaped_ln}</text>"
                )

    parts.append("</g></svg>")
    return "\n".join(parts)
