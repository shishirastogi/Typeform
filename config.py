import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _load_dotenv_file():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


_load_dotenv_file()


class Config:
    APP_NAME = os.environ.get("APP_NAME", "TYPEFORM")
    SECRET_KEY = os.environ.get(
        "SECRET_KEY", "typeform-editorial-studio-local-secret-key-2026"
    )
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads")
    )
    PROJECTS_FOLDER = os.path.join(UPLOAD_FOLDER, "projects")
    FONTS_FOLDER = os.path.join(BASE_DIR, "static", "fonts")

    MAX_CONTENT_LENGTH = int(
        os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)
    )
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    MAX_IMAGE_DIMENSIONS = (8000, 8000)
    MAX_IMAGE_PIXELS = 64_000_000
    WORKING_MASK_MAX_DIM = 1000
    MAX_EXPORT_DIMENSION = 8192
    FILE_CLEANUP_MAX_AGE_SECONDS = int(
        os.environ.get("FILE_CLEANUP_MAX_AGE_SECONDS", 86400)
    )

    SESSION_COOKIE_NAME = "typeform_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = FLASK_ENV == "production"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    DEFAULT_TEXT = (
        "Typography is the craft of endowing human language with a durable visual form. "
        "Structure emerges where rhythm meets restraint. Every rectangle acts as a brick "
        "in an architectural silhouette, locking syllables into contour, density, and space. "
        "Proportion governs the tension between positive ink and negative paper. "
        "When letterforms pack tightly along the threshold of light and shadow, "
        "a second image appears from language alone."
    )

    DEFAULT_SETTINGS = {
        # Text input settings
        "text": DEFAULT_TEXT,
        "repeat_text": True,
        "distribution_mode": "sequential",  # sequential | randomized | custom
        "custom_phrase": "TYPEFORM",
        # Canvas & Mask settings
        "canvas_width": 900,
        "canvas_height": 1125,
        "fill_mode": "silhouette",  # silhouette | rectangle
        "image_id": "builtin:portrait",
        "fit_mode": "fit",  # fit | fill | crop | stretch
        "threshold": 128,
        "contrast": 1.2,
        "invert_mask": False,
        "fg_mode": "auto",  # auto | alpha | dark_on_light | light_on_dark
        "image_scale": 1.0,
        "image_offset_x": 0.0,
        "image_offset_y": 0.0,
        "crop_left": 0.0,
        "crop_top": 0.0,
        "crop_right": 0.0,
        "crop_bottom": 0.0,
        "min_overlap": 0.55,
        # Typography settings
        "font_family": "Space Grotesk",
        "font_size": 15,
        "font_weight": "700",
        "font_style": "normal",
        "text_case": "uppercase",  # original | uppercase | lowercase | sentence
        "letter_spacing": 0.5,
        "line_height": 1.15,
        "text_align": "center",  # left | center | right
        "box_h_align": "center",  # left | center | right
        "box_v_align": "middle",  # top | middle | bottom
        # Text box dimensions & layout settings
        "layout_mode": "word_boxes",  # fixed_grid | word_boxes | variable_rows | dense | loose
        "box_width": 66,
        "box_height": 26,
        "min_box_width": 28,
        "max_box_width": 210,
        "h_spacing": 4,
        "v_spacing": 4,
        "padding_x": 6,
        "padding_y": 4,
        "row_offset": 0,
        "box_align": "center",  # left | center | right | justify
        "irregular_edge": 15,
        "word_wrap": "none",  # none | wrap
        "box_density": 1.0,
        "box_border_width": 0,
        # Color settings
        "color_mode": "random",  # monochrome | two_color | random | custom_palette | grayscale | gradient
        "background_color": "#F5F3EF",
        "transparent_bg": False,
        "primary_text_color": "#171717",
        "secondary_text_color": "#F5F3EF",
        "box_bg_color": "#171717",
        "box_border_color": "#171717",
        "palette": ["#171717", "#D9381E", "#DDD7CD", "#3D3A36", "#FFFFFF"],
        "palette_weights": [42, 18, 20, 12, 8],
        "apply_to": "box_and_text",  # box_and_text | box_only | text_only
        "seed": 42,
        # Export defaults
        "export_format": "png",
        "export_scale": 1,
        "export_jpg_quality": 95,
        "export_transparent": False,
        "export_bg_color": "#F5F3EF",
        "export_outline_text": False,
    }
