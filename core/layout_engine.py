import math
import random
from core.mask_generator import MaskData, build_mask
from core.typography import (
    WordStream,
    extract_word_tokens,
    measure_text_Cached,
    wrap_or_fit_word,
)


def _hex_to_rgb(hex_color: str) -> tuple:
    h = (hex_color or "#171717").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return (23, 23, 23)


def _rgb_to_hex(rgb: tuple) -> str:
    r, g, b = [max(0, min(255, int(round(v)))) for v in rgb]
    return f"#{r:02X}{g:02X}{b:02X}"


def _relative_luminance(hex_color: str) -> float:
    r, g, b = [v / 255.0 for v in _hex_to_rgb(hex_color)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _color_distance(hex1: str, hex2: str) -> float:
    r1, g1, b1 = _hex_to_rgb(hex1)
    r2, g2, b2 = _hex_to_rgb(hex2)
    return math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2)


def _contrasting_text_color(
    bg_hex: str, primary_text: str, secondary_text: str, box_idx: int = 0
) -> str:
    bg_lum = _relative_luminance(bg_hex)
    dist_p = _color_distance(bg_hex, primary_text)
    dist_s = _color_distance(bg_hex, secondary_text)

    p_norm = (primary_text or "#171717").upper()
    s_norm = (secondary_text or "#F5F3EF").upper()

    p_custom = p_norm != "#171717"
    s_custom = s_norm != "#F5F3EF"

    if p_custom and s_custom:
        # Both primary and secondary text colors were customized: use primary on even/light, secondary on odd/dark
        if box_idx % 2 == 0 and dist_p >= 35.0:
            return primary_text
        if dist_s >= 35.0:
            return secondary_text
        return primary_text if dist_p >= dist_s else secondary_text

    if p_custom:
        # User customized primary text color: apply it wherever distinguishable from the box fill
        if dist_p >= 40.0:
            return primary_text
        return secondary_text if dist_s >= 40.0 else ("#F5F3EF" if bg_lum < 0.5 else "#171717")

    if s_custom:
        # User customized secondary text color: apply it on dark boxes (or wherever distinguishable)
        if bg_lum < 0.55 and dist_s >= 40.0:
            return secondary_text
        if dist_p >= 45.0:
            return primary_text
        return secondary_text

    # Default editorial pairing (#171717 primary on light boxes, #F5F3EF secondary on dark boxes)
    if bg_lum < 0.48:
        return secondary_text if dist_s >= 45.0 else "#F5F3EF"
    return primary_text if dist_p >= 45.0 else "#171717"




def _interpolate_palette(palette: list, t: float) -> str:
    if not palette:
        return "#171717"
    if len(palette) == 1:
        return palette[0]
    t = max(0.0, min(1.0, float(t)))
    scaled = t * (len(palette) - 1)
    idx = int(math.floor(scaled))
    frac = scaled - idx
    if idx >= len(palette) - 1:
        return palette[-1]
    c1 = _hex_to_rgb(palette[idx])
    c2 = _hex_to_rgb(palette[idx + 1])
    mixed = (
        c1[0] + (c2[0] - c1[0]) * frac,
        c1[1] + (c2[1] - c1[1]) * frac,
        c1[2] + (c2[2] - c1[2]) * frac,
    )
    return _rgb_to_hex(mixed)


def _assign_box_colors(
    idx: int,
    x: float,
    y: float,
    w: float,
    h: float,
    canvas_w: int,
    canvas_h: int,
    settings: dict,
    color_rng: random.Random,
) -> tuple:
    """Return (box_fill_color, text_color) according to color_mode, palette, weights, and apply_to."""
    color_mode = settings.get("color_mode", "random")
    primary_text = settings.get("primary_text_color", "#171717")
    secondary_text = settings.get("secondary_text_color", "#F5F3EF")
    box_bg = settings.get("box_bg_color", "#171717")
    palette = list(settings.get("palette") or ["#171717", "#D9381E", "#DDD7CD", "#3D3A36", "#FFFFFF"])
    weights = list(settings.get("palette_weights") or [20] * len(palette))
    apply_to = settings.get("apply_to", "box_and_text")

    while len(weights) < len(palette):
        weights.append(20)
    weights = weights[: len(palette)]

    if color_mode == "monochrome":
        chosen = box_bg
    elif color_mode == "two_color":
        pair = [box_bg, secondary_text]
        w_pair = [weights[0] if weights else 50, weights[1] if len(weights) > 1 else 50]
        chosen = color_rng.choices(pair, weights=w_pair, k=1)[0]
    elif color_mode == "custom_palette":
        # Weighted deterministic cycle through custom palette
        chosen = palette[idx % len(palette)]
    elif color_mode == "grayscale":
        gray_ramp = ["#171717", "#2E2E2E", "#4A4845", "#77736F", "#C8C4BC", "#EAE6DF"]
        chosen = color_rng.choice(gray_ramp)
    elif color_mode == "gradient":
        nx = (x + w * 0.5) / max(1.0, float(canvas_w))
        ny = (y + h * 0.5) / max(1.0, float(canvas_h))
        t = 0.45 * nx + 0.55 * ny
        chosen = _interpolate_palette(palette, t)
    else:
        # "random" — strictly from the user's configured palette weighted by palette_weights
        chosen = color_rng.choices(palette, weights=weights, k=1)[0]

    if apply_to == "box_only":
        return (chosen, primary_text)
    elif apply_to == "text_only":
        return ("none", chosen)
    else:
        # "box_and_text"
        if color_mode == "monochrome":
            txt_c = _contrasting_text_color(chosen, primary_text, secondary_text, idx)
        elif color_mode == "two_color":
            if chosen == box_bg:
                txt_c = (
                    primary_text
                    if (primary_text or "").upper() != "#171717" and _color_distance(chosen, primary_text) >= 40.0
                    else secondary_text
                )
            else:
                txt_c = (
                    primary_text
                    if _color_distance(chosen, primary_text) >= 40.0
                    else box_bg
                )
            if _color_distance(txt_c, chosen) < 35.0:
                txt_c = _contrasting_text_color(chosen, primary_text, secondary_text, idx)
        else:
            txt_c = _contrasting_text_color(chosen, primary_text, secondary_text, idx)
        return (chosen, txt_c)


def _compute_text_anchor(
    box_x: float,
    box_y: float,
    box_w: float,
    box_h: float,
    text_w: float,
    cap_h: float,
    padding_x: float,
    padding_y: float,
    box_h_align: str,
    box_v_align: str,
) -> tuple:
    """Compute (text_x, text_y) inside a box for top-left or aligned text rendering."""
    inner_x0 = box_x + padding_x
    inner_x1 = box_x + box_w - padding_x
    inner_w = max(1.0, inner_x1 - inner_x0)

    if box_h_align == "left":
        tx = inner_x0
    elif box_h_align == "right":
        tx = max(inner_x0, inner_x1 - text_w)
    else:
        tx = inner_x0 + (inner_w - text_w) * 0.5

    inner_y0 = box_y + padding_y
    inner_y1 = box_y + box_h - padding_y
    inner_h = max(1.0, inner_y1 - inner_y0)

    if box_v_align == "top":
        ty = inner_y0 + cap_h * 0.5
    elif box_v_align == "bottom":
        ty = inner_y1 - cap_h * 0.5
    else:
        ty = box_y + box_h * 0.5

    return (round(tx, 2), round(ty, 2))


def generate_layout(settings: dict, mask_data: MaskData = None, file_path: str = None) -> dict:
    """
    Generate the complete rectangular text-box artwork geometry.
    Deterministic for a fixed settings['seed'].
    """
    if mask_data is None:
        mask_data = build_mask(settings, file_path=file_path)

    canvas_w = int(settings.get("canvas_width", 900))
    canvas_h = int(settings.get("canvas_height", 1125))
    layout_mode = settings.get("layout_mode", "word_boxes")

    box_w_setting = float(settings.get("box_width", 66))
    box_h_setting = float(settings.get("box_height", 26))
    min_box_w = float(settings.get("min_box_width", 28))
    max_box_w = float(settings.get("max_box_width", 210))
    h_spacing = float(settings.get("h_spacing", 4))
    v_spacing = float(settings.get("v_spacing", 4))
    padding_x = float(settings.get("padding_x", 6))
    padding_y = float(settings.get("padding_y", 4))
    row_offset = float(settings.get("row_offset", 0))
    box_align = settings.get("box_align", "center")
    irregular_edge = float(settings.get("irregular_edge", 15)) / 100.0
    word_wrap = settings.get("word_wrap", "none")
    box_density = float(settings.get("box_density", 1.0))
    min_overlap = float(settings.get("min_overlap", 0.55))
    border_width = int(settings.get("box_border_width", 0))
    border_color = settings.get("box_border_color", "#171717")

    font_family = settings.get("font_family", "Space Grotesk")
    base_font_size = int(settings.get("font_size", 15))
    font_weight = str(settings.get("font_weight", "700"))
    font_style = settings.get("font_style", "normal")
    letter_spacing = float(settings.get("letter_spacing", 0.5))
    line_height = float(settings.get("line_height", 1.15))
    text_align = settings.get("text_align", "center")
    box_h_align = settings.get("box_h_align", "center")
    box_v_align = settings.get("box_v_align", "middle")

    seed = int(settings.get("seed", 42))
    layout_rng = random.Random(seed)
    color_rng = random.Random(seed + 7919)

    tokens = extract_word_tokens(settings)
    if not tokens:
        return {
            "canvas_width": canvas_w,
            "canvas_height": canvas_h,
            "background_color": settings.get("background_color", "#F5F3EF"),
            "transparent_bg": bool(settings.get("transparent_bg", False)),
            "boxes": [],
            "stats": {
                "box_count": 0,
                "word_count": 0,
                "mask_coverage": round(mask_data.coverage_ratio * 100, 1),
                "seed": seed,
            },
        }

    word_stream = WordStream(
        tokens=tokens,
        repeat_text=bool(settings.get("repeat_text", True)),
        distribution_mode=settings.get("distribution_mode", "sequential"),
        seed=seed,
    )

    # Adjust effective spacing and dimensions per layout mode
    eff_h_spacing = h_spacing
    eff_v_spacing = v_spacing
    eff_min_w = min_box_w
    eff_max_w = max_box_w
    eff_row_h = max(12.0, box_h_setting)

    if layout_mode == "dense":
        eff_h_spacing = max(1.0, round(h_spacing * 0.5))
        eff_v_spacing = max(1.0, round(v_spacing * 0.5))
        eff_min_w = max(16.0, round(min_box_w * 0.75))
        eff_row_h = max(12.0, round(box_h_setting * 0.88))
    elif layout_mode == "loose":
        eff_h_spacing = round(h_spacing * 1.9 + 4.0)
        eff_v_spacing = round(v_spacing * 1.7 + 4.0)

    # Width scale factor relative to the default 66px reference box width
    width_scale = max(0.35, min(3.5, box_w_setting / 66.0))

    margin = 4.0
    y_cursor = margin
    row_idx = 0
    boxes = []
    box_id = 0
    max_boxes = 4500

    while y_cursor + eff_row_h <= canvas_h - margin and word_stream.has_more() and box_id < max_boxes:
        row_h = eff_row_h

        # Find active mask horizontal spans for this row band
        spans = mask_data.row_active_spans(y_cursor, row_h, min_density=max(0.1, min_overlap * 0.5))
        if not spans:
            y_cursor += row_h + eff_v_spacing
            row_idx += 1
            continue

        for span_start, span_end in spans:
            if not word_stream.has_more() or box_id >= max_boxes:
                break

            # Apply row offset and irregular edge jitter at segment boundaries
            jitter_amp = irregular_edge * box_w_setting * 0.55
            left_jitter = layout_rng.uniform(0.0, jitter_amp) if irregular_edge > 0 else 0.0
            right_jitter = layout_rng.uniform(0.0, jitter_amp) if irregular_edge > 0 else 0.0

            stagger = (row_offset if (row_idx % 2 == 1) else 0.0)

            seg_x0 = max(margin, span_start + left_jitter + stagger)
            seg_x1 = min(canvas_w - margin, span_end - right_jitter)

            if seg_x1 - seg_x0 < eff_min_w:
                continue

            row_segment_boxes = []
            x_cursor = seg_x0

            while x_cursor + eff_min_w <= seg_x1 and word_stream.has_more() and box_id < max_boxes:
                # Density check (allows controlled whitespace in loose mode or when box_density < 1.0)
                eff_density = box_density * (0.78 if layout_mode == "loose" else 1.0)
                if eff_density < 0.999 and layout_rng.random() > eff_density:
                    skip_step = max(12.0, box_w_setting * 0.45) + eff_h_spacing
                    x_cursor += skip_step
                    continue

                # Peek next word before committing placement
                word = word_stream.tokens[word_stream.index % len(word_stream.tokens)] if (
                    word_stream.distribution_mode != "randomized"
                ) else word_stream._shuffled_pool[word_stream.index % len(word_stream._shuffled_pool)]

                raw_text_w, cap_h = measure_text_Cached(
                    word, font_family, base_font_size, font_weight, font_style, letter_spacing
                )

                # Determine candidate box width & height based on layout_mode
                if layout_mode == "fixed_grid":
                    cand_w = box_w_setting
                elif layout_mode == "variable_rows":
                    extra_breath = layout_rng.uniform(0.0, irregular_edge * 22.0)
                    cand_w = (raw_text_w + 2.0 * padding_x) * width_scale + extra_breath
                    cand_w = max(eff_min_w, min(eff_max_w, cand_w))
                    # Ensure word fits if within max_box_w
                    if word_wrap == "none":
                        cand_w = max(cand_w, min(eff_max_w, raw_text_w + 2.0 * padding_x))
                elif layout_mode == "dense":
                    cand_w = max(eff_min_w, min(eff_max_w, raw_text_w + 2.0 * max(2.0, padding_x * 0.75)))
                else:
                    # word_boxes or loose
                    scaled_w = (raw_text_w + 2.0 * padding_x) * width_scale
                    cand_w = max(eff_min_w, min(eff_max_w, scaled_w))
                    if word_wrap == "none":
                        cand_w = max(cand_w, min(eff_max_w, raw_text_w + 2.0 * padding_x))

                cand_w = round(cand_w, 1)

                # Ensure box stays within segment / canvas bounds
                if x_cursor + cand_w > canvas_w - margin:
                    break
                if x_cursor + cand_w > seg_x1 + (jitter_amp * 0.35):
                    # Try shrinking slightly if still above eff_min_w and fits word
                    avail_seg = seg_x1 - x_cursor
                    min_needed = max(eff_min_w, raw_text_w + 2.0 * padding_x) if layout_mode != "fixed_grid" else box_w_setting
                    if avail_seg >= min_needed:
                        cand_w = round(avail_seg, 1)
                    else:
                        break

                overlap = mask_data.box_overlap_ratio(x_cursor, y_cursor, cand_w, row_h)
                if overlap < min_overlap:
                    # Step forward along the row to find where the silhouette begins
                    step = 3.0 if layout_mode == "dense" else max(4.0, cand_w * 0.25)
                    x_cursor += step
                    continue

                # Commit word consumption
                actual_word = word_stream.next_word()
                if actual_word is None:
                    break

                # Calculate effective font size and wrapped lines so text NEVER clips box
                inner_avail_w = max(6.0, cand_w - 2.0 * padding_x)
                inner_avail_h = max(6.0, row_h - 2.0 * padding_y)

                lines = wrap_or_fit_word(
                    actual_word,
                    inner_avail_w,
                    font_family,
                    base_font_size,
                    font_weight,
                    font_style,
                    letter_spacing,
                    word_wrap=word_wrap,
                )

                eff_font_size = float(base_font_size)
                max_line_w = 0.0
                eff_cap_h = cap_h
                for ln in lines:
                    lw, ch_px = measure_text_Cached(
                        ln, font_family, int(round(eff_font_size)), font_weight, font_style, letter_spacing
                    )
                    if lw > max_line_w:
                        max_line_w = lw
                    eff_cap_h = ch_px

                # Scale down font size if longest line exceeds inner_avail_w or total line block exceeds inner_avail_h
                total_block_h = eff_cap_h * (1.0 + (len(lines) - 1) * line_height)
                if max_line_w > inner_avail_w or total_block_h > inner_avail_h:
                    ratio_w = inner_avail_w / max(1.0, max_line_w)
                    ratio_h = inner_avail_h / max(1.0, total_block_h)
                    scale_factor = min(ratio_w, ratio_h)
                    eff_font_size = max(5.0, math.floor(base_font_size * scale_factor))
                    max_line_w = 0.0
                    for ln in lines:
                        lw, ch_px = measure_text_Cached(
                            ln, font_family, int(round(eff_font_size)), font_weight, font_style, letter_spacing
                        )
                        if lw > max_line_w:
                            max_line_w = lw
                        eff_cap_h = ch_px

                fill_color, txt_color = _assign_box_colors(
                    box_id,
                    x_cursor,
                    y_cursor,
                    cand_w,
                    row_h,
                    canvas_w,
                    canvas_h,
                    settings,
                    color_rng,
                )

                box_item = {
                    "id": box_id,
                    "x": round(x_cursor, 1),
                    "y": round(y_cursor, 1),
                    "w": round(cand_w, 1),
                    "h": round(row_h, 1),
                    "text": actual_word,
                    "lines": lines,
                    "font_size": int(round(eff_font_size)),
                    "text_w": round(max_line_w, 2),
                    "cap_h": round(eff_cap_h, 2),
                    "fill": fill_color,
                    "text_color": txt_color,
                    "border_color": border_color,
                    "border_width": border_width,
                }
                row_segment_boxes.append(box_item)
                box_id += 1
                x_cursor += cand_w + eff_h_spacing

            # Apply horizontal row alignment (left, center, right, justify) within the active segment
            if row_segment_boxes:
                first_x = row_segment_boxes[0]["x"]
                last_box = row_segment_boxes[-1]
                group_end = last_box["x"] + last_box["w"]
                slack = seg_x1 - group_end

                if slack > 1.0:
                    if box_align in ("center", "right"):
                        shift = (slack * 0.5) if box_align == "center" else slack
                        # Verify shifted boxes still satisfy mask overlap
                        valid_shift = True
                        for b in row_segment_boxes:
                            if mask_data.box_overlap_ratio(b["x"] + shift, b["y"], b["w"], b["h"]) < min_overlap * 0.9:
                                valid_shift = False
                                break
                        if valid_shift:
                            for b in row_segment_boxes:
                                b["x"] = round(b["x"] + shift, 1)

                    elif box_align == "justify" and len(row_segment_boxes) > 1 and layout_mode != "fixed_grid":
                        # Distribute slack across box widths up to eff_max_w so row fills the contour span
                        per_box_extra = min(slack / len(row_segment_boxes), 18.0)
                        if per_box_extra > 0.5:
                            curr_x = first_x
                            for b in row_segment_boxes:
                                new_w = min(eff_max_w, round(b["w"] + per_box_extra, 1))
                                if curr_x + new_w <= canvas_w - margin:
                                    b["x"] = round(curr_x, 1)
                                    b["w"] = new_w
                                curr_x = b["x"] + b["w"] + eff_h_spacing

                # Finalize text anchor coordinates inside each box
                for b in row_segment_boxes:
                    tx, ty = _compute_text_anchor(
                        b["x"],
                        b["y"],
                        b["w"],
                        b["h"],
                        b["text_w"],
                        b["cap_h"],
                        padding_x,
                        padding_y,
                        box_h_align,
                        box_v_align,
                    )
                    b["text_x"] = tx
                    b["text_y"] = ty
                    b["h_align"] = box_h_align
                    b["v_align"] = box_v_align
                    b["text_align"] = text_align
                    boxes.append(b)

        y_cursor += row_h + eff_v_spacing
        row_idx += 1

    return {
        "canvas_width": canvas_w,
        "canvas_height": canvas_h,
        "background_color": settings.get("background_color", "#F5F3EF"),
        "transparent_bg": bool(settings.get("transparent_bg", False)),
        "font_family": font_family,
        "font_weight": font_weight,
        "font_style": font_style,
        "letter_spacing": letter_spacing,
        "line_height": line_height,
        "padding_x": padding_x,
        "padding_y": padding_y,
        "boxes": boxes,
        "stats": {
            "box_count": len(boxes),
            "word_count": len(tokens),
            "mask_coverage": round(mask_data.coverage_ratio * 100, 1),
            "seed": seed,
        },
    }
