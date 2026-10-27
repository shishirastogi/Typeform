import unittest
from config import Config
from core.layout_engine import generate_layout
from core.mask_generator import build_mask


class TestLayoutEngine(unittest.TestCase):
    def _base_settings(self, **overrides):
        s = dict(Config.DEFAULT_SETTINGS)
        s["canvas_width"] = 600
        s["canvas_height"] = 600
        s.update(overrides)
        return s

    def test_deterministic_seed_reproducibility(self):
        s1 = self._base_settings(seed=101, layout_mode="word_boxes", distribution_mode="randomized")
        s2 = self._base_settings(seed=101, layout_mode="word_boxes", distribution_mode="randomized")
        s3 = self._base_settings(seed=999, layout_mode="word_boxes", distribution_mode="randomized")

        layout1 = generate_layout(s1)
        layout2 = generate_layout(s2)
        layout3 = generate_layout(s3)

        self.assertEqual(layout1["boxes"], layout2["boxes"])
        self.assertNotEqual(layout1["boxes"], layout3["boxes"])

    def test_all_layout_modes_and_bounds(self):
        for mode in ("fixed_grid", "word_boxes", "variable_rows", "dense", "loose"):
            s = self._base_settings(layout_mode=mode, fill_mode="silhouette", image_id="builtin:circle")
            mask = build_mask(s)
            layout = generate_layout(s, mask_data=mask)
            boxes = layout["boxes"]
            self.assertGreater(len(boxes), 10, f"Mode {mode} produced too few boxes")

            for b in boxes:
                self.assertGreaterEqual(b["x"], 0.0)
                self.assertGreaterEqual(b["y"], 0.0)
                self.assertLessEqual(b["x"] + b["w"], s["canvas_width"])
                self.assertLessEqual(b["y"] + b["h"], s["canvas_height"])
                overlap = mask.box_overlap_ratio(b["x"], b["y"], b["w"], b["h"])
                self.assertGreaterEqual(overlap, s["min_overlap"] * 0.85)

    def test_repeat_text_disabled_stops_when_exhausted(self):
        short_text = "Alpha Beta Gamma Delta"
        s_no_repeat = self._base_settings(text=short_text, repeat_text=False, fill_mode="rectangle")
        s_repeat = self._base_settings(text=short_text, repeat_text=True, fill_mode="rectangle")

        layout_once = generate_layout(s_no_repeat)
        layout_many = generate_layout(s_repeat)

        self.assertEqual(len(layout_once["boxes"]), 4)
        self.assertGreater(len(layout_many["boxes"]), 20)

    def test_custom_phrase_and_case_transforms(self):
        s_upper = self._base_settings(
            distribution_mode="custom",
            custom_phrase="Hello, World!",
            text_case="uppercase",
            repeat_text=False,
            fill_mode="rectangle",
        )
        layout_upper = generate_layout(s_upper)
        self.assertEqual([b["text"] for b in layout_upper["boxes"]], ["HELLO,", "WORLD!"])

        s_lower = self._base_settings(
            distribution_mode="custom",
            custom_phrase="Hello, World!",
            text_case="lowercase",
            repeat_text=False,
            fill_mode="rectangle",
        )
        layout_lower = generate_layout(s_lower)
        self.assertEqual([b["text"] for b in layout_lower["boxes"]], ["hello,", "world!"])

    def test_random_color_mode_respects_custom_palette(self):
        custom_pal = ["#112233", "#445566", "#778899"]
        s = self._base_settings(
            color_mode="random",
            palette=custom_pal,
            palette_weights=[50, 30, 20],
            apply_to="box_and_text",
        )
        layout = generate_layout(s)
        allowed = set(custom_pal)
        for b in layout["boxes"]:
            self.assertIn(b["fill"], allowed)

    def test_all_color_modes_and_apply_targets(self):
        for cm in ("monochrome", "two_color", "random", "custom_palette", "grayscale", "gradient"):
            for target in ("box_and_text", "box_only", "text_only"):
                s = self._base_settings(color_mode=cm, apply_to=target)
                layout = generate_layout(s)
                self.assertGreater(len(layout["boxes"]), 0)
                if target == "text_only":
                    self.assertEqual(layout["boxes"][0]["fill"], "none")
                else:
                    self.assertTrue(layout["boxes"][0]["fill"].startswith("#"))

    def test_changing_primary_and_secondary_text_colors_updates_boxes(self):
        s_default = self._base_settings(primary_text_color="#171717", secondary_text_color="#F5F3EF")
        s_custom_p = self._base_settings(primary_text_color="#2563EB", secondary_text_color="#F5F3EF")
        s_custom_s = self._base_settings(primary_text_color="#171717", secondary_text_color="#FACC15")

        l_def = generate_layout(s_default)
        l_cp = generate_layout(s_custom_p)
        l_cs = generate_layout(s_custom_s)

        cp_text_colors = {b["text_color"] for b in l_cp["boxes"]}
        cs_text_colors = {b["text_color"] for b in l_cs["boxes"]}
        def_text_colors = {b["text_color"] for b in l_def["boxes"]}

        self.assertIn("#2563EB", cp_text_colors)
        self.assertIn("#FACC15", cs_text_colors)
        self.assertNotEqual(def_text_colors, cp_text_colors)
        self.assertNotEqual(def_text_colors, cs_text_colors)


    def test_empty_text_returns_empty_boxes_gracefully(self):
        s = self._base_settings(text="   ", distribution_mode="sequential")
        layout = generate_layout(s)
        self.assertEqual(layout["boxes"], [])
        self.assertEqual(layout["stats"]["box_count"], 0)


if __name__ == "__main__":
    unittest.main()
