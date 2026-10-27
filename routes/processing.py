from flask import Blueprint, jsonify, request
from config import Config
from core.image_processor import (
    image_to_data_url,
    load_normalized_image,
    transform_image_to_canvas,
)
from core.layout_engine import generate_layout
from core.mask_generator import build_mask, render_mask_preview
from core.project_store import load_project_state, save_project_state
from core.security import (
    BUILTIN_IMAGE_IDS,
    csrf_protect,
    ensure_session,
    get_image_metadata,
    is_valid_image_id,
    sanitize_settings,
)

processing_bp = Blueprint("processing", __name__)


def _resolve_authorized_image_path(image_id: str, sid: str):
    """Resolve image_id to (file_path, error_response_tuple)."""
    if not image_id or image_id in BUILTIN_IMAGE_IDS:
        return (None, None)
    if not is_valid_image_id(image_id):
        return (None, (jsonify({"error": "Invalid image identifier."}), 400))
    meta = get_image_metadata(Config.UPLOAD_FOLDER, image_id, session_id=sid)
    if not meta:
        return (
            None,
            (
                jsonify({"error": "Image not found or access denied for current session."}),
                403,
            ),
        )
    return (meta["file_path"], None)


@processing_bp.route("/api/process-mask", methods=["POST"])
@csrf_protect
def process_mask():
    sid = ensure_session()
    if not request.is_json:
        return jsonify({"error": "Expected JSON request body."}), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Malformed JSON payload."}), 400

    raw_image_id = payload.get("image_id")
    if raw_image_id is not None and not is_valid_image_id(str(raw_image_id)):
        return jsonify({"error": "Invalid image identifier format."}), 400

    base_settings = load_project_state()
    settings = sanitize_settings(payload, base_settings)

    file_path, err = _resolve_authorized_image_path(settings["image_id"], sid)
    if err:
        return err

    mask_data = build_mask(settings, file_path=file_path)
    mask_preview = render_mask_preview(mask_data)

    cw = settings["canvas_width"]
    ch = settings["canvas_height"]
    prev_w = 360
    prev_h = max(64, int(round(prev_w * ch / max(1, cw))))
    raw_img = load_normalized_image(
        file_path=file_path,
        builtin_id=settings["image_id"],
        target_size=(prev_w, prev_h),
    )
    src_canvas = transform_image_to_canvas(raw_img, settings, working_size=(prev_w, prev_h))
    source_preview = image_to_data_url(src_canvas, fmt="PNG")

    return (
        jsonify(
            {
                "image_id": settings["image_id"],
                "mask_preview": mask_preview,
                "source_preview": source_preview,
                "coverage_ratio": round(mask_data.coverage_ratio * 100, 1),
                "used_alpha": mask_data.used_alpha,
                "canvas_width": cw,
                "canvas_height": ch,
            }
        ),
        200,
    )


@processing_bp.route("/api/generate", methods=["POST"])
@csrf_protect
def generate_artwork():
    sid = ensure_session()
    if not request.is_json:
        return jsonify({"error": "Expected JSON request body."}), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Malformed JSON payload."}), 400

    raw_image_id = payload.get("image_id")
    if raw_image_id is not None and not is_valid_image_id(str(raw_image_id)):
        return jsonify({"error": "Invalid image identifier format."}), 400

    base_settings = load_project_state()
    settings = sanitize_settings(payload, base_settings)

    file_path, err = _resolve_authorized_image_path(settings["image_id"], sid)
    if err:
        return err

    mask_data = build_mask(settings, file_path=file_path)
    layout = generate_layout(settings, mask_data=mask_data, file_path=file_path)
    mask_preview = render_mask_preview(mask_data)

    save_project_state(settings)

    return (
        jsonify(
            {
                "layout": layout,
                "mask_preview": mask_preview,
                "settings": settings,
            }
        ),
        200,
    )
