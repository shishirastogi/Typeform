from flask import Blueprint, jsonify, make_response, request, session
from config import Config
from core.project_store import (
    load_project_state,
    reset_project_state,
    save_project_state,
)
from core.security import (
    csrf_protect,
    ensure_session,
    get_image_metadata,
)

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/api/project/save", methods=["POST"])
@csrf_protect
def save_project():
    ensure_session()
    if not request.is_json:
        return jsonify({"error": "Expected JSON request body."}), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Malformed JSON payload."}), 400

    settings_in = payload.get("settings", payload)
    saved = save_project_state(settings_in)

    resp = make_response(
        jsonify(
            {
                "status": "saved",
                "project_id": session.get("project_id", ""),
                "settings": saved,
            }
        ),
        200,
    )
    resp.set_cookie(
        "typeform_last_project",
        session.get("project_id", ""),
        max_age=7 * 86400,
        httponly=True,
        samesite="Lax",
        secure=(Config.FLASK_ENV == "production"),
    )
    return resp


@projects_bp.route("/api/project/load", methods=["GET", "POST"])
def load_project():
    sid = ensure_session()
    project_id = None
    if request.method == "POST" and request.is_json:
        body = request.get_json(silent=True) or {}
        if isinstance(body, dict):
            project_id = body.get("project_id")
    elif request.args.get("project_id"):
        project_id = request.args.get("project_id")

    settings = load_project_state(project_id)
    image_meta = None
    img_id = settings.get("image_id", "")
    if img_id and not img_id.startswith("builtin:") and img_id != "none":
        meta = get_image_metadata(Config.UPLOAD_FOLDER, img_id, session_id=sid)
        if meta:
            image_meta = {
                "image_id": meta["image_id"],
                "filename": meta["original_filename"],
                "width": meta["width"],
                "height": meta["height"],
                "format": meta["format"],
                "size_bytes": meta["size_bytes"],
                "has_alpha": meta.get("has_alpha", False),
            }
        else:
            settings["image_id"] = "builtin:portrait"

    return (
        jsonify(
            {
                "status": "loaded",
                "project_id": session.get("project_id", ""),
                "settings": settings,
                "image_meta": image_meta,
            }
        ),
        200,
    )


@projects_bp.route("/api/project/reset", methods=["POST"])
@csrf_protect
def reset_project():
    ensure_session()
    defaults = reset_project_state()
    return (
        jsonify(
            {
                "status": "reset",
                "project_id": session.get("project_id", ""),
                "settings": defaults,
            }
        ),
        200,
    )
