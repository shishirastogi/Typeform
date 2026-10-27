import io
import unittest
from PIL import Image, ImageDraw
from app import create_app
from config import Config
from core.security import is_valid_image_id, resolve_safe_path


class TestSecurityAndPersistence(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client_a = self.app.test_client()
        self.client_b = self.app.test_client()

        self.client_a.get("/")
        with self.client_a.session_transaction() as sess_a:
            self.csrf_a = sess_a["csrf_token"]

        self.client_b.get("/")
        with self.client_b.session_transaction() as sess_b:
            self.csrf_b = sess_b["csrf_token"]

    def _make_sample_png_bytes(self):
        img = Image.new("RGBA", (160, 160), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((20, 20, 140, 140), fill=(0, 0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_csrf_required_on_state_changing_endpoints(self):
        # Missing CSRF token must return 403
        for endpoint in (
            "/api/generate",
            "/api/process-mask",
            "/api/export",
            "/api/project/save",
            "/api/project/reset",
        ):
            resp = self.client_a.post(endpoint, json={"text": "hello"})
            self.assertEqual(resp.status_code, 403, f"Expected 403 on {endpoint} without CSRF")

    def test_path_traversal_protection(self):
        with self.assertRaises(ValueError):
            resolve_safe_path(Config.UPLOAD_FOLDER, "../app.py")
        with self.assertRaises(ValueError):
            resolve_safe_path(Config.UPLOAD_FOLDER, "..\\config.py")
        self.assertFalse(is_valid_image_id("../../etc/passwd"))
        self.assertFalse(is_valid_image_id("12345/../abcdef"))

        resp = self.client_a.post(
            "/api/process-mask",
            json={"image_id": "../../secret.png"},
            headers={"X-CSRF-Token": self.csrf_a},
        )
        self.assertEqual(resp.status_code, 400)

    def test_session_ownership_isolation_for_uploaded_images(self):
        png_bytes = self._make_sample_png_bytes()
        upload_resp = self.client_a.post(
            "/api/upload",
            data={"file": (io.BytesIO(png_bytes), "silhouette.png")},
            headers={"X-CSRF-Token": self.csrf_a},
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 200)
        up_data = upload_resp.get_json()
        image_id = up_data["image_id"]

        # Client A can generate using its own uploaded image
        gen_a = self.client_a.post(
            "/api/generate",
            json={"image_id": image_id},
            headers={"X-CSRF-Token": self.csrf_a},
        )
        self.assertEqual(gen_a.status_code, 200)

        # Client B (different session) must be denied access to Client A's uploaded image
        gen_b = self.client_b.post(
            "/api/generate",
            json={"image_id": image_id},
            headers={"X-CSRF-Token": self.csrf_b},
        )
        self.assertEqual(gen_b.status_code, 403)

    def test_project_save_load_and_reset_cycle(self):
        save_resp = self.client_a.post(
            "/api/project/save",
            json={
                "settings": {
                    "text": "Custom Saved Editorial Text",
                    "box_width": 88,
                    "seed": 777,
                }
            },
            headers={"X-CSRF-Token": self.csrf_a},
        )
        self.assertEqual(save_resp.status_code, 200)

        load_resp = self.client_a.get("/api/project/load")
        self.assertEqual(load_resp.status_code, 200)
        loaded = load_resp.get_json()["settings"]
        self.assertEqual(loaded["text"], "Custom Saved Editorial Text")
        self.assertEqual(loaded["box_width"], 88)
        self.assertEqual(loaded["seed"], 777)

        reset_resp = self.client_a.post(
            "/api/project/reset",
            json={},
            headers={"X-CSRF-Token": self.csrf_a},
        )
        self.assertEqual(reset_resp.status_code, 200)
        reset_settings = reset_resp.get_json()["settings"]
        self.assertEqual(reset_settings["box_width"], 66)
        self.assertEqual(reset_settings["seed"], 42)

    def test_page_routes_render_cleanly(self):
        for route in ("/", "/guide", "/about"):
            resp = self.client_a.get(route)
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b"TYPEFORM", resp.data)



if __name__ == "__main__":
    unittest.main()
