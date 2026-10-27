import io
import unittest
import xml.etree.ElementTree as ET
from PIL import Image
from app import create_app
from config import Config


class TestExports(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        # Initialize session and obtain CSRF token
        self.client.get("/")
        with self.client.session_transaction() as sess:
            self.csrf_token = sess["csrf_token"]

    def _export_request(self, fmt, scale, extra=None):
        settings = dict(Config.DEFAULT_SETTINGS)
        settings["canvas_width"] = 300
        settings["canvas_height"] = 400
        settings["text"] = "Typography <Art> & \"Design\" Studio"
        payload = {
            "settings": settings,
            "export_format": fmt,
            "export_scale": scale,
            "export_transparent": False,
            "export_bg_color": "#F5F3EF",
            "export_jpg_quality": 92,
            "export_outline_text": False,
        }
        if extra:
            payload.update(extra)
        return self.client.post(
            "/api/export",
            json=payload,
            headers={"X-CSRF-Token": self.csrf_token},
        )

    def test_png_exports_at_1x_2x_3x_4x(self):
        for scale in (1, 2, 3, 4):
            resp = self._export_request("png", scale)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.mimetype, "image/png")
            with Image.open(io.BytesIO(resp.data)) as img:
                self.assertEqual(img.size, (300 * scale, 400 * scale))

    def test_png_transparent_background(self):
        resp = self._export_request("png", 1, {"export_transparent": True})
        self.assertEqual(resp.status_code, 200)
        with Image.open(io.BytesIO(resp.data)) as img:
            self.assertEqual(img.mode, "RGBA")
            # Corner pixel (0, 0) outside silhouette should be transparent
            self.assertEqual(img.getpixel((0, 0))[3], 0)

    def test_jpg_exports_at_1x_2x_3x_4x(self):
        for scale in (1, 2, 3, 4):
            resp = self._export_request("jpg", scale, {"export_transparent": True})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.mimetype, "image/jpeg")
            with Image.open(io.BytesIO(resp.data)) as img:
                self.assertEqual(img.size, (300 * scale, 400 * scale))
                self.assertEqual(img.mode, "RGB")

    def test_svg_exports_at_1x_2x_3x_4x_and_escapes_xml(self):
        for scale in (1, 2, 3, 4):
            resp = self._export_request("svg", scale)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.mimetype, "image/svg+xml")
            svg_text = resp.data.decode("utf-8")
            # Must parse as valid XML even with special characters <, >, &, " in input text
            root = ET.fromstring(svg_text)
            self.assertEqual(root.attrib.get("width"), str(300 * scale))
            self.assertEqual(root.attrib.get("height"), str(400 * scale))
            self.assertEqual(root.attrib.get("viewBox"), f"0 0 {300 * scale} {400 * scale}")

    def test_svg_outline_text_conversion(self):
        resp = self._export_request("svg", 1, {"export_outline_text": True})
        self.assertEqual(resp.status_code, 200)
        svg_text = resp.data.decode("utf-8")
        self.assertIn("<path ", svg_text)
        root = ET.fromstring(svg_text)
        self.assertEqual(root.attrib.get("width"), "300")

    def test_invalid_export_parameters_rejected(self):
        resp_bad_scale = self._export_request("png", 5)
        self.assertEqual(resp_bad_scale.status_code, 400)

        resp_bad_fmt = self._export_request("tiff", 1)
        self.assertEqual(resp_bad_fmt.status_code, 400)


if __name__ == "__main__":
    unittest.main()
