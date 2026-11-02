import colorsys
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from trp_strata import palette
from trp_strata.color_extraction import from_oklab, to_oklab, select, clusters


class PaletteTests(unittest.TestCase):
    def test_perceptual_conversion_roundtrip(self):
        for rgb in ((0, 0, 0), (1, 1, 1), (1, 0, 0), (0, 1, 0), (0, 0, 1), (.3, .5, .8)):
            for actual, expected in zip(from_oklab(to_oklab(rgb)), rgb):
                self.assertAlmostEqual(actual, expected, places=5)

    def test_tiny_specks_do_not_replace_main_accent(self):
        samples = [(210, .6, .5)] * 995 + [(0, 1, .5)] * 5
        self.assertLess(palette.hue_distance(select(samples)[2], 210), 5)

    def test_meaningful_contrasting_colour_becomes_accent(self):
        samples = [(210, .55, .45)] * 850 + [(15, .85, .5)] * 150
        dominant, _, accent, _, mono = select(samples)
        self.assertFalse(mono)
        self.assertLess(palette.hue_distance(dominant, 210), 5)
        self.assertLess(palette.hue_distance(accent, 15), 5)

    def test_muted_wallpapers_keep_soft_colours(self):
        samples = [(160, .2, .65)] * 100
        _, _, _, saturation, mono = select(samples)
        self.assertFalse(mono)
        self.assertLess(saturation, .3)
        for theme in palette.build(samples).values():
            _, _, s = colorsys.rgb_to_hls(*palette.hex_to_rgb(theme["accent"]))
            self.assertLess(s, .3)

    def test_grayscale_and_empty_images_have_neutral_accents(self):
        for samples in ([], [(0, 0, .1)] * 50 + [(0, 0, .8)] * 50, [(0, 0, 1)]):
            for theme in palette.build(samples).values():
                for key in ("paper", "accent", "accent_text"):
                    rgb = palette.hex_to_rgb(theme[key])
                    self.assertLessEqual(max(rgb) - min(rgb), 1 / 255)

    def test_order_independence_and_red_hue_wrap(self):
        samples = [(359, .8, .5)] * 100 + [(1, .8, .5)] * 100 + [(180, .3, .5)] * 5
        original = palette.build(samples)
        random.Random(1).shuffle(samples)
        self.assertEqual(palette.build(samples), original)
        self.assertLess(palette.hue_distance(select(samples)[2], 0), 5)

    def test_generated_theme_text_contrast_across_hues(self):
        for hue in range(0, 360, 15):
            for saturation in (0, .2, .6, 1):
                for lightness in (.15, .5, .85):
                    for mode, theme in palette.build([(hue, saturation, lightness)] * 10).items():
                        with self.subTest(hue=hue, saturation=saturation, lightness=lightness, mode=mode):
                            for background in ("paper", "sheet"):
                                for foreground in ("ink", "muted", "accent_text"):
                                    self.assertGreaterEqual(palette.contrast(theme[foreground], theme[background]), 4.5)
                            self.assertGreaterEqual(palette.contrast(theme["on_accent"], theme["accent"]), 4.5)

    def test_clustering_is_bounded(self):
        rng = random.Random(7)
        samples = [(rng.random() * 360, rng.random(), rng.random()) for _ in range(14400)]
        groups = clusters(samples)
        self.assertLessEqual(len(groups), 32)
        self.assertEqual(sum(count for _, count in groups), len(samples))

    def test_transparent_pixels_are_excluded(self):
        try:
            import gi
            gi.require_version("GdkPixbuf", "2.0")
            from gi.repository import GdkPixbuf, GLib
        except ImportError:
            self.skipTest("GdkPixbuf is unavailable")
        image = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes((255, 0, 0, 0, 0, 0, 255, 255))),
                                              GdkPixbuf.Colorspace.RGB, True, 8, 2, 1, 8)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "transparent.png")
            image.savev(path, "png", [], [])
            samples = palette.image_colors(path, size=2)
        self.assertEqual(len(samples), 1)
        self.assertLess(palette.hue_distance(samples[0][0], 240), 1)

    def test_cached_palettes_upgrade_once_and_keep_previous_colours_on_error(self):
        try:
            from trp_strata import core
        except ImportError:
            self.skipTest("Gio is unavailable")
        old, new = palette.build([]), palette.build([(210, .5, .5)])
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "wallpaper.png"
            source.write_bytes(b"placeholder; image decoding is mocked")
            state = {"still": str(source), "palette": old}
            with patch.object(palette, "from_image", return_value=new) as extract:
                core._refresh_palette(state)
                self.assertEqual(state["palette"], new)
                self.assertEqual(state["palette_version"], palette.EXTRACTION_VERSION)
                core._refresh_palette(state)
                extract.assert_called_once_with(str(source))
            state = {"still": str(source), "palette": old}
            with patch.object(palette, "from_image", side_effect=ValueError("bad image")), self.assertLogs("trp_strata.core", level="WARNING"):
                core._refresh_palette(state)
            self.assertIs(state["palette"], old)
            self.assertNotIn("palette_version", state)
            source.unlink()
            with patch.object(palette, "from_image") as extract:
                core._refresh_palette(state)
                extract.assert_not_called()


if __name__ == "__main__":
    unittest.main()
