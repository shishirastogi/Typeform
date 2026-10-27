import json
import os
import time
import uuid
from flask import Blueprint, jsonify, request
from config import Config
from core.image_processor import (
    image_to_data_url,
    load_normalized_image,
    transform_image_to_canvas,
    validate_and_inspect_image,
)
from core.mask_generator import build_mask, render_mask_preview
from core.project_store import load_project_state, save_project_state
from core.security import (
    cleanup_old_files,
    csrf_protect,
    ensure_session,
    get_image_metadata,
    is_allowed_extension,
    resolve_safe_path,
    sanitize_filename_safe,
)

upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/api/upload", methods=["POST"])
@csrf_protect
def upload_image():
    sid = ensure_session()
    cleanup_old_files(Config.UPLOAD_FOLDER)

    if "file" not in request.files:
        return jsonify({"error": "No image file provided in request."}), 400

    file_obj = request.files["file"]
    if not file_obj or not file_obj.filename:
        return jsonify({"error": "No file selected."}), 400

    original_filename = sanitize_filename_safe(file_obj.filename)
    if not is_allowed_extension(original_filename):
        return (
            jsonify(
                {
                    "error": "Unsupported file type. Please upload PNG, JPG, JPEG, or WebP."
                }
            ),
            400,
        )

    file_bytes = file_obj.read()
    try:
        info = validate_and_inspect_image(file_bytes, original_filename)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    ext = original_filename.rsplit(".", 1)[1].lower()
    image_id = uuid.uuid4().hex
    stored_filename = f"{image_id}.{ext}"

    try:
        img_path = resolve_safe_path(Config.UPLOAD_FOLDER, stored_filename)
        meta_path = resolve_safe_path(Config.UPLOAD_FOLDER, f"{image_id}.json")
        with open(img_path, "wb") as fh:
            fh.write(file_bytes)

        meta_record = {
            "image_id": image_id,
            "owner_sid": sid,
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "width": info["width"],
            "height": info["height"],
            "format": info["format"],
            "mode": info["mode"],
            "has_alpha": info["has_alpha"],
            "size_bytes": info["size_bytes"],
            "created_at": time.time(),
        }
        with open(meta_path, "w", encoding="utf-8") as mfh:
            json.dump(meta_record, mfh, indent=2)
    except (OSError, ValueError) as exc:
        return jsonify({"error": f"Failed to store uploaded image: {exc}"}), 500

    # Update project settings with the newly uploaded image_id
    settings = load_project_state()
    settings["image_id"] = image_id
    settings["fill_mode"] = "silhouette"
    save_project_state(settings)

    mask_data = build_mask(settings, file_path=img_path)
    mask_preview = render_mask_preview(mask_data)

    raw_img = load_normalized_image(file_path=img_path)
    src_canvas = transform_image_to_canvas(raw_img, settings, working_size=(360, int(round(360 * settings["canvas_height"] / max(1, settings["canvas_width"])))))
    source_preview = image_to_data_url(src_canvas, fmt="PNG")

    return jsonify(
        {
            "image_id": image_id,
            "filename": original_filename,
            "width": info["width"],
            "height": info["height"],
            "format": info["format"],
            "size_bytes": info["size_bytes"],
            "has_alpha": info["has_alpha"],
            "mask_preview": mask_preview,
            "source_preview": source_preview,
            "coverage_ratio": round(mask_data.coverage_ratio * 100, 1),
        }
    ), 200


@upload_bp.route("/api/upload/remove", methods=["POST"])
@csrf_protect
def remove_uploaded_image():
    sid = ensure_session()
    payload = request.get_json(silent=True) or {}
    image_id = payload.get("image_id", "")
    fallback_id = payload.get("fallback_id", "builtin:portrait")
    if fallback_id not in ("builtin:portrait", "builtin:circle", "builtin:arch", "builtin:monolith", "builtin:diamond", "none"):
        fallback_id = "builtin:portrait"

    if image_id and not str(image_id).startswith("builtin:"):
        meta = get_image_metadata(Config.UPLOAD_FOLDER, str(image_id), session_id=sid)
        if meta:
            for fname in (meta.get("stored_filename", ""), f"{image_id}.json"):
                if fname:
                    try:
                        p = resolve_safe_path(Config.UPLOAD_FOLDER, fname)
                        if os.path.isfile(p):
                            os.remove(p)
                    except (OSError, ValueError):
                        pass

    settings = load_project_state()
    settings["image_id"] = fallback_id
    save_project_state(settings)

    return jsonify({"status": "removed", "image_id": fallback_id}), 200
