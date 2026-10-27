from flask import Blueprint, render_template, session
from config import Config
from core.project_store import load_project_state
from core.security import ensure_session, get_csrf_token, get_image_metadata

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", methods=["GET"])
def index():
    sid = ensure_session()
    settings = load_project_state()
    image_meta = None
    image_id = settings.get("image_id", "")
    if image_id and not image_id.startswith("builtin:") and image_id != "none":
        meta = get_image_metadata(Config.UPLOAD_FOLDER, image_id, session_id=sid)
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

    return render_template(
        "index.html",
        app_name=Config.APP_NAME,
        active_page="editor",
        initial_settings=settings,
        initial_image_meta=image_meta,
        csrf_token=get_csrf_token(),
        project_id=session.get("project_id", ""),
    )


@pages_bp.route("/guide", methods=["GET"])
def guide():
    ensure_session()
    return render_template(
        "guide.html",
        app_name=Config.APP_NAME,
        active_page="guide",
        csrf_token=get_csrf_token(),
    )


@pages_bp.route("/about", methods=["GET"])
def about():
    ensure_session()
    return render_template(
        "about.html",
        app_name=Config.APP_NAME,
        active_page="about",
        csrf_token=get_csrf_token(),
    )
