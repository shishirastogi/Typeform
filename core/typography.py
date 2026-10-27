import os
import random
import re
from functools import lru_cache
from PIL import ImageFont
from config import Config

BUNDLED_FONT_MAP = {
    ("Space Grotesk", "400", "normal"): "SpaceGrotesk-Regular.ttf",
    ("Space Grotesk", "700", "normal"): "SpaceGrotesk-Bold.ttf",
    ("Space Grotesk", "400", "italic"): "SpaceGrotesk-Italic.ttf",
    ("Space Grotesk", "700", "italic"): "SpaceGrotesk-Italic.ttf",
    ("Neue Machina", "400", "normal"): "NeueMachina-Regular.ttf",
    ("Neue Machina", "700", "normal"): "NeueMachina-Bold.ttf",
    ("Neue Machina", "400", "italic"): "NeueMachina-Italic.ttf",
    ("Neue Machina", "700", "italic"): "NeueMachina-Italic.ttf",
    ("DejaVu Sans", "400", "normal"): "DejaVuSans.ttf",
    ("DejaVu Sans", "700", "normal"): "DejaVuSans-Bold.ttf",
    ("DejaVu Sans", "400", "italic"): "DejaVuSans-Oblique.ttf",
    ("DejaVu Sans", "700", "italic"): "DejaVuSans-Oblique.ttf",
    ("DejaVu Sans Mono", "400", "normal"): "DejaVuSansMono.ttf",
    ("DejaVu Sans Mono", "700", "normal"): "DejaVuSansMono-Bold.ttf",
    ("DejaVu Sans Mono", "400", "italic"): "DejaVuSansMono-Oblique.ttf",
    ("DejaVu Sans Mono", "700", "italic"): "DejaVuSansMono-Oblique.ttf",
    ("DejaVu Serif", "400", "normal"): "DejaVuSerif.ttf",
    ("DejaVu Serif", "700", "normal"): "DejaVuSerif-Bold.ttf",
    ("DejaVu Serif", "400", "italic"): "DejaVuSerif-Italic.ttf",
    ("DejaVu Serif", "700", "italic"): "DejaVuSerif-Italic.ttf",
}

SYSTEM_FONT_CANDIDATES = {
    ("Bahnschrift", "400", "normal"): ["bahnschrift.ttf", "SpaceGrotesk-Regular.ttf"],
    ("Bahnschrift", "700", "normal"): ["bahnschrift.ttf", "SpaceGrotesk-Bold.ttf"],
    ("Bahnschrift", "400", "italic"): ["bahnschrift.ttf", "SpaceGrotesk-Italic.ttf"],
    ("Bahnschrift", "700", "italic"): ["bahnschrift.ttf", "SpaceGrotesk-Bold.ttf"],
    ("Arial", "400", "normal"): ["arial.ttf", "DejaVuSans.ttf"],
    ("Arial", "700", "normal"): ["arialbd.ttf", "DejaVuSans-Bold.ttf"],
    ("Arial", "400", "italic"): ["ariali.ttf", "DejaVuSans-Oblique.ttf"],
    ("Arial", "700", "italic"): ["arialbi.ttf", "DejaVuSans-Oblique.ttf"],
    ("Courier New", "400", "normal"): ["cour.ttf", "DejaVuSansMono.ttf"],
    ("Courier New", "700", "normal"): ["courbd.ttf", "DejaVuSansMono-Bold.ttf"],
    ("Courier New", "400", "italic"): ["couri.ttf", "DejaVuSansMono-Oblique.ttf"],
    ("Courier New", "700", "italic"): ["courbi.ttf", "DejaVuSansMono-Oblique.ttf"],
    ("Georgia", "400", "normal"): ["georgia.ttf", "DejaVuSerif.ttf"],
    ("Georgia", "700", "normal"): ["georgiab.ttf", "DejaVuSerif-Bold.ttf"],
    ("Georgia", "400", "italic"): ["georgiai.ttf", "DejaVuSerif-Italic.ttf"],
    ("Georgia", "700", "italic"): ["georgiaz.ttf", "DejaVuSerif-Italic.ttf"],
    ("Impact", "400", "normal"): ["impact.ttf", "SpaceGrotesk-Bold.ttf"],
    ("Impact", "700", "normal"): ["impact.ttf", "SpaceGrotesk-Bold.ttf"],
    ("Impact", "400", "italic"): ["impact.ttf", "SpaceGrotesk-Bold.ttf"],
    ("Impact", "700", "italic"): ["impact.ttf", "SpaceGrotesk-Bold.ttf"],
}


@lru_cache(maxsize=128)
def resolve_font_path(
    font_family: str = "Space Grotesk",
    font_weight: str = "700",
    font_style: str = "normal",
) -> str:
    """Resolve font family, weight, and style to an existing local .ttf path."""
    w = "700" if str(font_weight) in ("700", "bold") else "400"
    s = "italic" if str(font_style) == "italic" else "normal"
    key = (font_family, w, s)

    if key in BUNDLED_FONT_MAP:
        candidate = os.path.join(Config.FONTS_FOLDER, BUNDLED_FONT_MAP[key])
        if os.path.isfile(candidate):
            return candidate

    if key in SYSTEM_FONT_CANDIDATES:
        for fname in SYSTEM_FONT_CANDIDATES[key]:
            win_path = os.path.join(r"C:\Windows\Fonts", fname)
            if os.path.isfile(win_path):
                return win_path
            bundled_path = os.path.join(Config.FONTS_FOLDER, fname)
            if os.path.isfile(bundled_path):
                return bundled_path

    # Fallback to bundled Space Grotesk or DejaVu Sans
    fallback_name = "SpaceGrotesk-Bold.ttf" if w == "700" else "SpaceGrotesk-Regular.ttf"
    fallback_path = os.path.join(Config.FONTS_FOLDER, fallback_name)
    if os.path.isfile(fallback_path):
        return fallback_path

    dejavu_path = os.path.join(Config.FONTS_FOLDER, "DejaVuSans.ttf")
    return dejavu_path


@lru_cache(maxsize=256)
def get_pil_font(
    font_family: str = "Space Grotesk",
    font_size: int = 15,
    font_weight: str = "700",
    font_style: str = "normal",
):
    """Load and cache a Pillow FreeTypeFont instance."""
    size = max(4, min(400, int(round(font_size))))
    path = resolve_font_path(font_family, font_weight, font_style)
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


@lru_cache(maxsize=8192)
def measure_text_Cached(
    text: str,
    font_family: str = "Space Grotesk",
    font_size: int = 15,
    font_weight: str = "700",
    font_style: str = "normal",
    letter_spacing: float = 0.0,
) -> tuple:
    """Return (width, cap_height) in pixels for a given string and font configuration."""
    if not text:
        return (0.0, float(font_size))
    font = get_pil_font(font_family, font_size, font_weight, font_style)
    try:
        length = float(font.getlength(text))
    except AttributeError:
        bbox = font.getbbox(text)
        length = float(bbox[2] - bbox[0]) if bbox else float(len(text) * font_size * 0.6)

    if len(text) > 1 and abs(letter_spacing) > 1e-4:
        length += (len(text) - 1) * float(letter_spacing)

    # Cap / visual height estimate from uppercase reference
    try:
        ref_bbox = font.getbbox("HG")
        cap_h = float(ref_bbox[3] - ref_bbox[1]) if ref_bbox else float(font_size * 0.72)
    except Exception:
        cap_h = float(font_size * 0.72)

    return (max(1.0, round(length, 2)), max(1.0, round(cap_h, 2)))


def apply_case_transform(words: list, text_case: str) -> list:
    """Transform list of word tokens according to text_case setting."""
    if not words:
        return []
    if text_case == "uppercase":
        return [w.upper() for w in words]
    if text_case == "lowercase":
        return [w.lower() for w in words]
    if text_case == "sentence":
        out = []
        capitalize_next = True
        for w in words:
            lower_w = w.lower()
            if capitalize_next and lower_w:
                # Capitalize first alphabetic character
                chars = list(lower_w)
                for idx, ch in enumerate(chars):
                    if ch.isalpha():
                        chars[idx] = ch.upper()
                        break
                out.append("".join(chars))
            else:
                out.append(lower_w)
            capitalize_next = bool(re.search(r"[.!?][\"'\)\]]*$", w))
        return out
    # "original"
    return list(words)


def extract_word_tokens(settings: dict) -> list:
    """Extract and case-transform word tokens preserving punctuation."""
    dist_mode = settings.get("distribution_mode", "sequential")
    if dist_mode == "custom":
        raw_source = (settings.get("custom_phrase") or "").strip()
        if not raw_source:
            raw_source = (settings.get("text") or "").strip()
    else:
        raw_source = (settings.get("text") or "").strip()

    if not raw_source:
        return []

    # Collapse whitespace into clean word tokens while preserving punctuation
    tokens = [tok for tok in re.split(r"\s+", raw_source) if tok]
    text_case = settings.get("text_case", "uppercase")
    return apply_case_transform(tokens, text_case)


class WordStream:
    """Deterministic generator yielding words according to repeat and distribution settings."""

    def __init__(self, tokens: list, repeat_text: bool, distribution_mode: str, seed: int):
        self.tokens = list(tokens)
        self.repeat_text = bool(repeat_text)
        self.distribution_mode = distribution_mode
        self.rng = random.Random(int(seed) + 101)
        self.index = 0
        self._shuffled_pool = list(self.tokens)
        if self.distribution_mode == "randomized" and len(self._shuffled_pool) > 1:
            self.rng.shuffle(self._shuffled_pool)

    def has_more(self) -> bool:
        if not self.tokens:
            return False
        if self.repeat_text:
            return True
        return self.index < len(self.tokens)

    def next_word(self):
        if not self.has_more():
            return None
        if self.distribution_mode == "randomized":
            if not self.repeat_text:
                word = self._shuffled_pool[self.index]
                self.index += 1
                return word
            idx = self.index % len(self._shuffled_pool)
            if idx == 0 and self.index > 0 and len(self._shuffled_pool) > 1:
                self.rng.shuffle(self._shuffled_pool)
            word = self._shuffled_pool[idx]
            self.index += 1
            return word
        else:
            word = self.tokens[self.index % len(self.tokens)]
            self.index += 1
            return word


def wrap_or_fit_word(
    word: str,
    avail_w: float,
    font_family: str,
    font_size: int,
    font_weight: str,
    font_style: str,
    letter_spacing: float,
    word_wrap: str = "none",
) -> list:
    """Split a word into multiple lines if word_wrap == 'wrap' and word exceeds avail_w."""
    if not word:
        return [""]
    w_px, _ = measure_text_Cached(
        word, font_family, font_size, font_weight, font_style, letter_spacing
    )
    if word_wrap != "wrap" or w_px <= avail_w or len(word) <= 2:
        return [word]

    lines = []
    current = ""
    for ch in word:
        candidate = current + ch
        cw_px, _ = measure_text_Cached(
            candidate, font_family, font_size, font_weight, font_style, letter_spacing
        )
        if cw_px <= max(avail_w, font_size) or not current:
            current = candidate
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines[:3]  # Cap at 3 lines per box for clean legibility
