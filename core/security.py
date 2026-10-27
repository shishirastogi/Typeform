import hmac
import json
import os
import re
import secrets
import time
import uuid
from functools import wraps
from flask import current_app, jsonify, request, session
from werkzeug.utils import secure_filename
from config import Config

HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
IMAGE_ID_RE = re.compile(r"^[a-f0-9]{32}$")
BUILTIN_IMAGE_IDS = {
    "builtin:portrait",
    "builtin:circle",
    "builtin:arch",
    "builtin:monolith",
    "builtin:diamond",
    "none",
    "",
}


def ensure_session():
    """Ensure the current Flask session has a unique session ID, project ID, and CSRF token."""
    session.permanent = True
    if "sid" not in session or not isinstance(session.get("sid"), str):
        session["sid"] = uuid.uuid4().hex
    if "project_id" not in session or not isinstance(session.get("project_id"), str):
        session["project_id"] = uuid.uuid4().hex
    if "csrf_token" not in session or not isinstance(session.get("csrf_token"), str):
        session["csrf_token"] = secrets.token_hex(24)
    return session["sid"]


def get_csrf_token():
    ensure_session()
    return session["csrf_token"]


def verify_csrf_request():
    """Verify CSRF token on state-changing requests."""
    ensure_session()
    expected = session.get("csrf_token", "")
    if not expected:
        return False
    token = request.headers.get("X-CSRF-Token", "")
    if not token and request.is_json:
        data = request.get_json(silent=True) or {}
        if isinstance(data, dict):
            token = str(data.get("csrf_token", ""))
    if not token and request.form:
        token = request.form.get("csrf_token", "")
    if not token or not isinstance(token, str):
        return False
    return hmac.compare_digest(token, expected)


def csrf_protect(fn):
    """Decorator enforcing CSRF verification on POST/PUT/DELETE routes."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            if not verify_csrf_request():
                return jsonify({"error": "Invalid or missing CSRF token."}), 403
        return fn(*args, **kwargs)
    return wrapper


def sanitize_filename_safe(filename: str) -> str:
    if not filename:
        return "upload.png"
    cleaned = secure_filename(filename)
    return cleaned if cleaned else "upload.png"


def is_allowed_extension(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in Config.ALLOWED_EXTENSIONS


def is_valid_image_id(image_id: str) -> bool:
    if not isinstance(image_id, str):
        return False
    if image_id in BUILTIN_IMAGE_IDS:
        return True
    return bool(IMAGE_ID_RE.match(image_id))


def resolve_safe_path(base_folder: str, filename: str) -> str:
    """Resolve path inside base_folder and prevent any path traversal."""
    base_real = os.path.realpath(base_folder)
    os.makedirs(base_real, exist_ok=True)
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError("Invalid filename traversal detected.")
    candidate = os.path.realpath(os.path.join(base_real, filename))
    if not candidate.startswith(base_real + os.sep) and candidate != base_real:
        raise ValueError("Path traversal attempt blocked.")
    return candidate


def get_image_metadata(upload_folder: str, image_id: str, session_id: str = None):
    """Load uploaded image metadata and enforce session ownership."""
    if not IMAGE_ID_RE.match(image_id or ""):
        return None
    try:
        meta_path = resolve_safe_path(upload_folder, f"{image_id}.json")
    except ValueError:
        return None
    if not os.path.isfile(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return None
    if session_id is not None and meta.get("owner_sid") != session_id:
        return None
    img_filename = meta.get("stored_filename", "")
    try:
        img_path = resolve_safe_path(upload_folder, img_filename)
    except ValueError:
        return None
    if not os.path.isfile(img_path):
        return None
    meta["file_path"] = img_path
    return meta


def cleanup_old_files(upload_folder: str, max_age_seconds: int = None):
    """Remove abandoned uploads and temporary project files older than max_age_seconds."""
    if max_age_seconds is None:
        max_age_seconds = Config.FILE_CLEANUP_MAX_AGE_SECONDS
    now = time.time()
    removed = 0
    for folder in (upload_folder, os.path.join(upload_folder, "projects")):
        if not os.path.isdir(folder):
            continue
        try:
            for entry in os.scandir(folder):
                if not entry.is_file():
                    continue
                if entry.name.startswith("."):
                    continue
                try:
                    stat = entry.stat()
                    if now - stat.st_mtime > max_age_seconds:
                        os.remove(entry.path)
                        removed += 1
                except OSError:
                    pass
        except OSError:
            pass
    return removed


def normalize_hex_color(value, default="#171717") -> str:
    if not isinstance(value, str):
        return default
    val = value.strip()
    if not HEX_COLOR_RE.match(val):
        return default
    if len(val) == 4:
        r, g, b = val[1], val[2], val[3]
        return f"#{r}{r}{g}{g}{b}{b}".upper()
    return val.upper()


def _clamp_int(val, low, high, default):
    try:
        v = int(round(float(val)))
        return max(low, min(high, v))
    except (TypeError, ValueError):
        return default


def _clamp_float(val, low, high, default):
    try:
        v = float(val)
        if v != v:  # NaN check
            return default
        return max(low, min(high, v))
    except (TypeError, ValueError):
        return default


def _to_bool(val, default=False):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(val, (int, float)):
        return bool(val)
    return default


def sanitize_settings(incoming: dict, base: dict = None) -> dict:
    """Validate and sanitize user project settings against allowed values and bounds."""
    defaults = dict(Config.DEFAULT_SETTINGS)
    if isinstance(base, dict):
        defaults.update(base)
    if not isinstance(incoming, dict):
        return defaults

    out = dict(defaults)

    # Text settings
    if "text" in incoming and isinstance(incoming["text"], str):
        out["text"] = incoming["text"][:50000]
    if "repeat_text" in incoming:
        out["repeat_text"] = _to_bool(incoming["repeat_text"], out["repeat_text"])
    if incoming.get("distribution_mode") in ("sequential", "randomized", "custom"):
        out["distribution_mode"] = incoming["distribution_mode"]
    if "custom_phrase" in incoming and isinstance(incoming["custom_phrase"], str):
        out["custom_phrase"] = incoming["custom_phrase"][:500]

    # Canvas & Mask settings
    if "canvas_width" in incoming:
        out["canvas_width"] = _clamp_int(incoming["canvas_width"], 200, 2400, out["canvas_width"])
    if "canvas_height" in incoming:
        out["canvas_height"] = _clamp_int(incoming["canvas_height"], 200, 2400, out["canvas_height"])
    if incoming.get("fill_mode") in ("silhouette", "rectangle"):
        out["fill_mode"] = incoming["fill_mode"]
    if "image_id" in incoming and is_valid_image_id(str(incoming["image_id"])):
        out["image_id"] = str(incoming["image_id"])
    if incoming.get("fit_mode") in ("fit", "fill", "crop", "stretch"):
        out["fit_mode"] = incoming["fit_mode"]
    if "threshold" in incoming:
        out["threshold"] = _clamp_int(incoming["threshold"], 0, 255, out["threshold"])
    if "contrast" in incoming:
        out["contrast"] = round(_clamp_float(incoming["contrast"], 0.2, 4.0, out["contrast"]), 2)
    if "invert_mask" in incoming:
        out["invert_mask"] = _to_bool(incoming["invert_mask"], out["invert_mask"])
    if incoming.get("fg_mode") in ("auto", "alpha", "dark_on_light", "light_on_dark"):
        out["fg_mode"] = incoming["fg_mode"]
    if "image_scale" in incoming:
        out["image_scale"] = round(_clamp_float(incoming["image_scale"], 0.2, 3.0, out["image_scale"]), 2)
    if "image_offset_x" in incoming:
        out["image_offset_x"] = round(_clamp_float(incoming["image_offset_x"], -100.0, 100.0, out["image_offset_x"]), 1)
    if "image_offset_y" in incoming:
        out["image_offset_y"] = round(_clamp_float(incoming["image_offset_y"], -100.0, 100.0, out["image_offset_y"]), 1)
    for crop_key in ("crop_left", "crop_top", "crop_right", "crop_bottom"):
        if crop_key in incoming:
            out[crop_key] = round(_clamp_float(incoming[crop_key], 0.0, 45.0, out[crop_key]), 1)
    if "min_overlap" in incoming:
        out["min_overlap"] = round(_clamp_float(incoming["min_overlap"], 0.05, 1.0, out["min_overlap"]), 2)

    # Typography settings
    allowed_fonts = {
        "Space Grotesk",
        "Neue Machina",
        "DejaVu Sans",
        "DejaVu Sans Mono",
        "DejaVu Serif",
        "Bahnschrift",
        "Arial",
        "Courier New",
        "Georgia",
        "Impact",
    }
    if incoming.get("font_family") in allowed_fonts:
        out["font_family"] = incoming["font_family"]
    if "font_size" in incoming:
        out["font_size"] = _clamp_int(incoming["font_size"], 6, 96, out["font_size"])
    if str(incoming.get("font_weight")) in ("400", "700", "normal", "bold"):
        w = str(incoming["font_weight"])
        out["font_weight"] = "700" if w in ("700", "bold") else "400"
    if incoming.get("font_style") in ("normal", "italic"):
        out["font_style"] = incoming["font_style"]
    if incoming.get("text_case") in ("original", "uppercase", "lowercase", "sentence"):
        out["text_case"] = incoming["text_case"]
    if "letter_spacing" in incoming:
        out["letter_spacing"] = round(_clamp_float(incoming["letter_spacing"], -4.0, 20.0, out["letter_spacing"]), 2)
    if "line_height" in incoming:
        out["line_height"] = round(_clamp_float(incoming["line_height"], 0.7, 3.0, out["line_height"]), 2)
    if incoming.get("text_align") in ("left", "center", "right"):
        out["text_align"] = incoming["text_align"]
    if incoming.get("box_h_align") in ("left", "center", "right"):
        out["box_h_align"] = incoming["box_h_align"]
    if incoming.get("box_v_align") in ("top", "middle", "bottom"):
        out["box_v_align"] = incoming["box_v_align"]

    # Box & Layout settings
    if incoming.get("layout_mode") in ("fixed_grid", "word_boxes", "variable_rows", "dense", "loose"):
        out["layout_mode"] = incoming["layout_mode"]
    if "box_width" in incoming:
        out["box_width"] = _clamp_int(incoming["box_width"], 16, 400, out["box_width"])
    if "box_height" in incoming:
        out["box_height"] = _clamp_int(incoming["box_height"], 10, 200, out["box_height"])
    if "min_box_width" in incoming:
        out["min_box_width"] = _clamp_int(incoming["min_box_width"], 12, 300, out["min_box_width"])
    if "max_box_width" in incoming:
        out["max_box_width"] = _clamp_int(incoming["max_box_width"], 20, 600, out["max_box_width"])
    if out["min_box_width"] > out["max_box_width"]:
        out["min_box_width"], out["max_box_width"] = out["max_box_width"], out["min_box_width"]
    if "h_spacing" in incoming:
        out["h_spacing"] = _clamp_int(incoming["h_spacing"], 0, 80, out["h_spacing"])
    if "v_spacing" in incoming:
        out["v_spacing"] = _clamp_int(incoming["v_spacing"], 0, 80, out["v_spacing"])
    if "padding_x" in incoming:
        out["padding_x"] = _clamp_int(incoming["padding_x"], 0, 60, out["padding_x"])
    if "padding_y" in incoming:
        out["padding_y"] = _clamp_int(incoming["padding_y"], 0, 60, out["padding_y"])
    if "row_offset" in incoming:
        out["row_offset"] = _clamp_int(incoming["row_offset"], -200, 200, out["row_offset"])
    if incoming.get("box_align") in ("left", "center", "right", "justify"):
        out["box_align"] = incoming["box_align"]
    if "irregular_edge" in incoming:
        out["irregular_edge"] = _clamp_int(incoming["irregular_edge"], 0, 100, out["irregular_edge"])
    if incoming.get("word_wrap") in ("none", "wrap"):
        out["word_wrap"] = incoming["word_wrap"]
    if "box_density" in incoming:
        out["box_density"] = round(_clamp_float(incoming["box_density"], 0.1, 1.0, out["box_density"]), 2)
    if "box_border_width" in incoming:
        out["box_border_width"] = _clamp_int(incoming["box_border_width"], 0, 10, out["box_border_width"])

    # Color settings
    if incoming.get("color_mode") in (
        "monochrome",
        "two_color",
        "random",
        "custom_palette",
        "grayscale",
        "gradient",
    ):
        out["color_mode"] = incoming["color_mode"]
    for color_key in (
        "background_color",
        "primary_text_color",
        "secondary_text_color",
        "box_bg_color",
        "box_border_color",
        "export_bg_color",
    ):
        if color_key in incoming:
            out[color_key] = normalize_hex_color(incoming[color_key], out[color_key])
    if "transparent_bg" in incoming:
        out["transparent_bg"] = _to_bool(incoming["transparent_bg"], out["transparent_bg"])
    if "palette" in incoming and isinstance(incoming["palette"], list):
        clean_pal = []
        for c in incoming["palette"][:12]:
            if isinstance(c, str) and HEX_COLOR_RE.match(c.strip()):
                clean_pal.append(normalize_hex_color(c.strip()))
        if clean_pal:
            out["palette"] = clean_pal
    if "palette_weights" in incoming and isinstance(incoming["palette_weights"], list):
        weights = []
        for w in incoming["palette_weights"][:12]:
            weights.append(_clamp_int(w, 1, 100, 20))
        out["palette_weights"] = weights
    # Match weights length to palette length
    while len(out["palette_weights"]) < len(out["palette"]):
        out["palette_weights"].append(20)
    out["palette_weights"] = out["palette_weights"][: len(out["palette"])]

    if incoming.get("apply_to") in ("box_and_text", "box_only", "text_only"):
        out["apply_to"] = incoming["apply_to"]
    if "seed" in incoming:
        out["seed"] = _clamp_int(incoming["seed"], 0, 9999999, out["seed"])

    # Export settings
    if incoming.get("export_format") in ("svg", "png", "jpg"):
        out["export_format"] = incoming["export_format"]
    if "export_scale" in incoming:
        out["export_scale"] = _clamp_int(incoming["export_scale"], 1, 4, out["export_scale"])
    if "export_jpg_quality" in incoming:
        out["export_jpg_quality"] = _clamp_int(incoming["export_jpg_quality"], 10, 100, out["export_jpg_quality"])
    if "export_transparent" in incoming:
        out["export_transparent"] = _to_bool(incoming["export_transparent"], out["export_transparent"])
    if "export_outline_text" in incoming:
        out["export_outline_text"] = _to_bool(incoming["export_outline_text"], out["export_outline_text"])

    return out
