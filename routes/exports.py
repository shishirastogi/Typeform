from flask import Blueprint, Response, jsonify, request
from config import Config
from core.layout_engine import generate_layout
from core.mask_generator import build_mask
from core.project_store import load_project_state
from core.raster_renderer import render_raster
from core.security import (
    BUILTIN_IMAGE_IDS,
    csrf_protect,
    ensure_session,
    get_image_metadata,
    is_valid_image_id,
    normalize_hex_color,
    sanitize_settings,
)
from core.svg_renderer import render_svg

exports_bp = Blueprint("exports", __name__)


@exports_bp.route("/api/export", methods=["POST"])
@csrf_protect
def export_artwork():
    sid = ensure_session()
    if not request.is_json:
        return jsonify({"error": "Expected JSON request body."}), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Malformed JSON payload."}), 400

    # Validate format explicitly
    raw_fmt = str(payload.get("export_format") or payload.get("format") or "png").strip().lower()
    if raw_fmt == "jpeg":
        raw_fmt = "jpg"
    if raw_fmt not in ("svg", "png", "jpg"):
        return jsonify({"error": f"Unsupported export format '{raw_fmt}'. Choose svg, png, or jpg."}), 400

    # Validate scale explicitly
    raw_scale = payload.get("export_scale", payload.get("scale", 1))
    try:
        scale = int(raw_scale)
    except (TypeError, ValueError):
        return jsonify({"error": "Export scale multiplier must be an integer (1, 2, 3, or 4)."}), 400
    if scale not in (1, 2, 3, 4):
        return jsonify({"error": "Export scale multiplier must be 1, 2, 3, or 4."}), 400

    base_settings = load_project_state()
    settings_in = payload.get("settings", payload)
    if not isinstance(settings_in, dict):
        return jsonify({"error": "Invalid settings object."}), 400

    raw_image_id = settings_in.get("image_id")
    if raw_image_id is not None and not is_valid_image_id(str(raw_image_id)):
        return jsonify({"error": "Invalid image identifier."}), 400

    settings = sanitize_settings(settings_in, base_settings)

    # Check export dimensions before rendering
    out_w = int(settings["canvas_width"]) * scale
    out_h = int(settings["canvas_height"]) * scale
    if out_w > Config.MAX_EXPORT_DIMENSION or out_h > Config.MAX_EXPORT_DIMENSION:
        return (
            jsonify(
                {
                    "error": f"Export resolution ({out_w}x{out_h}) exceeds maximum allowed dimension ({Config.MAX_EXPORT_DIMENSION}px)."
                }
            ),
            400,
        )

    # Resolve image path and enforce session ownership
    file_path = None
    img_id = settings["image_id"]
    if img_id and img_id not in BUILTIN_IMAGE_IDS:
        meta = get_image_metadata(Config.UPLOAD_FOLDER, img_id, session_id=sid)
        if not meta:
            return jsonify({"error": "Image not found or unauthorized."}), 403
        file_path = meta["file_path"]

    transparent = bool(payload.get("export_transparent", payload.get("transparent", settings.get("transparent_bg", False))))
    bg_color = normalize_hex_color(
        payload.get("export_bg_color", payload.get("bg_color", settings.get("background_color", "#F5F3EF"))),
        settings.get("background_color", "#F5F3EF"),
    )
    jpg_quality = payload.get("export_jpg_quality", payload.get("jpg_quality", settings.get("export_jpg_quality", 95)))
    try:
        jpg_quality = max(10, min(100, int(jpg_quality)))
    except (TypeError, ValueError):
        jpg_quality = 95

    outline_text = bool(payload.get("export_outline_text", payload.get("outline_text", settings.get("export_outline_text", False))))

    mask_data = build_mask(settings, file_path=file_path)
    layout = generate_layout(settings, mask_data=mask_data, file_path=file_path)

    filename = f"typeform-{out_w}x{out_h}-{scale}x.{raw_fmt}"

    if raw_fmt == "svg":
        svg_str = render_svg(
            layout=layout,
            scale=scale,
            transparent=transparent,
            bg_color=bg_color,
            outline_text=outline_text,
        )
        svg_bytes = svg_str.encode("utf-8")
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Width": str(out_w),
            "X-Export-Height": str(out_h),
            "X-Export-Scale": str(scale),
            "X-Export-Format": "svg",
        }
        return Response(svg_bytes, status=200, mimetype="image/svg+xml", headers=headers)

    try:
        img_bytes, actual_w, actual_h, mime = render_raster(
            layout=layout,
            fmt=raw_fmt,
            scale=scale,
            transparent=transparent,
            bg_color=bg_color,
            jpg_quality=jpg_quality,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Export-Width": str(actual_w),
        "X-Export-Height": str(actual_h),
        "X-Export-Scale": str(scale),
        "X-Export-Format": raw_fmt,
    }
    return Response(img_bytes, status=200, mimetype=mime, headers=headers)
