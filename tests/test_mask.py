import io
import unittest
import numpy as np
from PIL import Image, ImageDraw
from config import Config
from core.image_processor import validate_and_inspect_image
from core.mask_generator import build_mask, render_mask_preview


class TestMaskProcessing(unittest.TestCase):
    def _create_image_bytes(self, fmt="PNG", mode="RGB", size=(200, 200), bg=(255, 255, 255), fg=(10, 10, 10)):
        img = Image.new(mode, size, bg)
        draw = ImageDraw.Draw(img)
        draw.rectangle((50, 50, 150, 150), fill=fg)
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()

    def test_validate_valid_formats(self):
        for fmt in ("PNG", "JPEG", "WEBP"):
            raw = self._create_image_bytes(fmt=fmt, mode="RGB")
            info = validate_and_inspect_image(raw, f"sample.{fmt.lower()}")
            self.assertEqual(info["width"], 200)
            self.assertEqual(info["height"], 200)
            self.assertEqual(info["format"], fmt)

    def test_validate_corrupted_and_empty_files(self):
        with self.assertRaises(ValueError):
            validate_and_inspect_image(b"", "empty.png")
        with self.assertRaises(ValueError):
            validate_and_inspect_image(b"not-an-image-file-content", "bad.png")

    def test_validate_unsupported_format(self):
        img = Image.new("RGB", (64, 64), (255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="BMP")
        with self.assertRaises(ValueError) as ctx:
            validate_and_inspect_image(buf.getvalue(), "test.bmp")
        self.assertIn("Unsupported image format", str(ctx.exception))

    def test_transparent_png_alpha_detection(self):
        raw = self._create_image_bytes(
            fmt="PNG",
            mode="RGBA",
            size=(200, 200),
            bg=(255, 255, 255, 0),
            fg=(20, 20, 20, 255),
        )
        info = validate_and_inspect_image(raw, "alpha.png")
        self.assertTrue(info["has_alpha"])

    def test_silhouette_vs_rectangle_mask(self):
        settings = dict(Config.DEFAULT_SETTINGS)
        settings["canvas_width"] = 400
        settings["canvas_height"] = 400
        settings["fill_mode"] = "silhouette"
        settings["image_id"] = "builtin:circle"
        settings["invert_mask"] = False

        sil_mask = build_mask(settings, use_cache=False)
        self.assertGreater(sil_mask.coverage_ratio, 0.25)
        self.assertLess(sil_mask.coverage_ratio, 0.75)

        # Center of circle should have 1.0 overlap; corner should have 0.0 overlap
        center_overlap = sil_mask.box_overlap_ratio(180, 180, 40, 40)
        corner_overlap = sil_mask.box_overlap_ratio(0, 0, 30, 30)
        self.assertEqual(center_overlap, 1.0)
        self.assertEqual(corner_overlap, 0.0)

        # Invert mask flips center and corner
        settings["invert_mask"] = True
        inv_mask = build_mask(settings, use_cache=False)
        self.assertAlmostEqual(sil_mask.coverage_ratio + inv_mask.coverage_ratio, 1.0, places=2)
        self.assertEqual(inv_mask.box_overlap_ratio(180, 180, 40, 40), 0.0)
        self.assertEqual(inv_mask.box_overlap_ratio(0, 0, 30, 30), 1.0)

        # Rectangle mode fills entire canvas
        settings["fill_mode"] = "rectangle"
        rect_mask = build_mask(settings, use_cache=False)
        self.assertEqual(rect_mask.coverage_ratio, 1.0)

    def test_mask_preview_data_url(self):
        settings = dict(Config.DEFAULT_SETTINGS)
        mask_data = build_mask(settings)
        data_url = render_mask_preview(mask_data)
        self.assertTrue(data_url.startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
