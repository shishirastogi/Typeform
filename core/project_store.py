import json
import os
import time
from flask import session
from config import Config
from core.security import (
    IMAGE_ID_RE,
    ensure_session,
    resolve_safe_path,
    sanitize_settings,
)


def _get_project_file_path(project_id: str) -> str:
    if not IMAGE_ID_RE.match(project_id or ""):
        raise ValueError("Invalid project identifier.")
    return resolve_safe_path(Config.PROJECTS_FOLDER, f"{project_id}.json")


def save_project_state(settings: dict, project_id: str = None) -> dict:
    """Persist sanitized project settings for the active session."""
    sid = ensure_session()
    pid = project_id if (project_id and IMAGE_ID_RE.match(project_id)) else session.get("project_id")
    clean = sanitize_settings(settings)

    # Save compact preferences in Flask session cookie (excluding large text)
    compact_prefs = {
        "font_family": clean["font_family"],
        "layout_mode": clean["layout_mode"],
        "color_mode": clean["color_mode"],
        "fill_mode": clean["fill_mode"],
        "box_width": clean["box_width"],
        "h_spacing": clean["h_spacing"],
        "v_spacing": clean["v_spacing"],
        "image_id": clean["image_id"],
        "seed": clean["seed"],
    }
    session["prefs"] = compact_prefs
    session["project_id"] = pid
    session.modified = True

    record = {
        "project_id": pid,
        "owner_sid": sid,
        "updated_at": time.time(),
        "settings": clean,
    }
    try:
        path = _get_project_file_path(pid)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)
    except (OSError, ValueError):
        pass

    return clean


def load_project_state(project_id: str = None) -> dict:
    """Load saved project settings for the active session or return defaults."""
    sid = ensure_session()
    pid = project_id if (project_id and IMAGE_ID_RE.match(project_id)) else session.get("project_id")
    base = dict(Config.DEFAULT_SETTINGS)

    if isinstance(session.get("prefs"), dict):
        base = sanitize_settings(session["prefs"], base)

    if pid and IMAGE_ID_RE.match(pid):
        try:
            path = _get_project_file_path(pid)
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as fh:
                    record = json.load(fh)
                if record.get("owner_sid") == sid and isinstance(record.get("settings"), dict):
                    return sanitize_settings(record["settings"], base)
        except (OSError, ValueError):
            pass

    return base


def reset_project_state() -> dict:
    """Reset the current session's project state back to default prototype settings."""
    sid = ensure_session()
    pid = session.get("project_id")
    defaults = dict(Config.DEFAULT_SETTINGS)
    session.pop("prefs", None)
    session.modified = True
    if pid and IMAGE_ID_RE.match(pid):
        try:
            path = _get_project_file_path(pid)
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as fh:
                    record = json.load(fh)
                if record.get("owner_sid") == sid:
                    os.remove(path)
        except (OSError, ValueError):
            pass
    save_project_state(defaults, pid)
    return defaults
