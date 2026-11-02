import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from trp_strata import layout, settings, storage
from trp_strata.components import resolve


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for name, value in {"CONFIG_DIR": self.temp.name, "LAYOUT": str(Path(self.temp.name) / "layout.json"),
                            "CUSTOM_WIDGETS": str(Path(self.temp.name) / "widgets"),
                            "LOCK": str(Path(self.temp.name) / ".lock")}.items():
            p = patch.object(storage, name, value)
            p.start()
            self.addCleanup(p.stop)
        layout.ensure_layout()
        p = patch.object(settings, "CONFIG", str(Path(self.temp.name) / "config.json"))
        p.start()
        self.addCleanup(p.stop)

    def test_default_layout_and_offsets(self):
        entries = layout.load_layout()
        self.assertEqual([item.component for item in entries], ["Clock", "Calendar", "System", "Cleaner", "Notes", "NowPlaying", "Logtime", "Launcher", "FileSearch", "QuickLinks", "Volume", "Brightness"])
        self.assertEqual(layout.coordinates(entries[0], 1000, 800, 200, 100, 48), (400, 48))
        self.assertEqual(layout.coordinates(entries[1], 1000, 800, 200, 100), (768, 32))
        self.assertEqual(layout.coordinates(entries[4], 1000, 800, 200, 100), (768, 668))
        self.assertEqual(layout.coordinates(entries[6], 1000, 800, 200, 100), (32, 668))

    def test_now_playing_preserves_custom_placements_when_added(self):
        default = json.loads(layout.DEFAULT_FILE.read_text())
        previous = {**default, "widgets": [entry for entry in default["widgets"]
                                           if entry["component"] != "NowPlaying"]}
        Path(storage.LAYOUT).write_text(json.dumps(previous))
        layout.ensure_layout()
        self.assertEqual(json.loads(Path(storage.LAYOUT).read_text()), default)
        previous["widgets"][0]["x"] = 123
        Path(storage.LAYOUT).write_text(json.dumps(previous))
        layout.ensure_layout()
        upgraded = json.loads(Path(storage.LAYOUT).read_text())
        self.assertEqual(upgraded["widgets"][:-1], previous["widgets"])
        self.assertEqual(upgraded["widgets"][-1]["component"], "NowPlaying")
        layout.set_enabled("now-playing", False)
        layout.ensure_layout()
        self.assertFalse(layout.load_layout()[-1].enabled)
        self.assertEqual(layout.widget_title(layout.load_layout()[-1]), "Now playing")

    def test_grid_footprints_gutters_and_screen_edges(self):
        width = layout.grid_extent(201, 32, 8)
        self.assertEqual(width, 232)
        self.assertEqual(layout.grid_extent(width, 32, 8), width)
        left = layout.grid_coordinate(8, width, 1000, 32, 8)
        adjacent = layout.grid_coordinate(left + width + 8, width, 1000, 32, 8)
        self.assertEqual(adjacent - left - width, 8)
        self.assertEqual(layout.grid_coordinate(-500, width, 1000, 32, 8), 8)
        right = layout.grid_coordinate(2000, width, 1000, 32, 8)
        self.assertLessEqual(right + width + 8, 1000)
        self.assertEqual((right - 8) % 40, 0)
        self.assertEqual(layout.grid_coordinate(100, 2000, 1000, 32, 8), 0)
        self.assertEqual(layout.grid_extent(64, 32, 0), 64)

    def test_launcher_upgrade_preserves_custom_layout_and_handles_id_collision(self):
        document = {"version": 1, "widgets": [
            {"id": "launcher", "component": "Notes", "x": 123, "enabled": False},
            {"id": "music", "component": "NowPlaying", "enabled": False},
            {"id": "file-search", "component": "FileSearch", "enabled": False},
            {"id": "quick-links", "component": "QuickLinks", "enabled": False},
            {"id": "volume", "component": "Volume", "enabled": False},
            {"id": "brightness", "component": "Brightness", "enabled": False},
        ]}
        Path(storage.LAYOUT).write_text(json.dumps(document))
        layout.ensure_layout()
        upgraded = json.loads(Path(storage.LAYOUT).read_text())
        self.assertEqual(upgraded["widgets"][:-1], document["widgets"])
        launcher = layout.load_layout()[-1]
        self.assertEqual((launcher.id, launcher.component, launcher.enabled), ("launcher-2", "Launcher", False))
        layout.set_enabled(launcher.id, True)
        layout.ensure_layout()
        self.assertTrue(layout.load_layout()[-1].enabled)
        self.assertEqual(len(layout.load_layout()), 7)

    def test_resize_hit_testing_covers_all_edges_and_corners(self):
        points = {"nw": (2, 2), "n": (100, 2), "ne": (198, 2), "w": (2, 60),
                  "e": (198, 60), "sw": (2, 118), "s": (100, 118), "se": (198, 118)}
        for edges, point in points.items():
            self.assertEqual(layout.resize_edges(*point, 200, 120), edges)
        self.assertEqual(layout.resize_edges(100, 60, 200, 120), "")
        self.assertEqual(layout.resize_edges(-1, 60, 200, 120), "")

    def test_independent_resize_preserves_opposite_edges(self):
        rect = (100, 100, 300, 200)
        for edges in ("n", "s", "e", "w", "nw", "ne", "sw", "se"):
            with self.subTest(edges=edges):
                x, y, w, h = layout.resize_rectangle(rect, 30, 20, edges, (60, 40), (1000, 800))
                self.assertEqual(w, 270 if "w" in edges else 330 if "e" in edges else 300)
                self.assertEqual(h, 180 if "n" in edges else 220 if "s" in edges else 200)
                self.assertEqual(x + w, 430 if "e" in edges else 400)
                self.assertEqual(y + h, 320 if "s" in edges else 300)

    def test_grid_resize_limits_content_and_work_area(self):
        rect = (88, 88, 232, 152)
        self.assertEqual(layout.resize_rectangle(rect, 45, 0, "e", (100, 50), (1000, 800), 32, 8),
                         (88, 88, 272, 152))
        self.assertEqual(layout.resize_rectangle(rect, 1000, 1000, "nw", (100, 50), (1000, 800), 32, 8),
                         (208, 168, 112, 72))
        x, y, w, h = layout.resize_rectangle(rect, 10000, 10000, "se", (100, 50), (1000, 800), 32, 8)
        self.assertLessEqual(x + w + 8, 1000)
        self.assertLessEqual(y + h + 8, 800)
        self.assertEqual((w + 8) % 40, 0)
        self.assertEqual((h + 8) % 40, 0)

    def test_dimensions_roundtrip_without_changing_scale(self):
        layout.save_placement("notes", width=250, height=180)
        entry = next(p for p in layout.load_layout() if p.id == "notes")
        self.assertEqual((entry.width, entry.height, entry.scale), (250, 180, 1))
        layout.save_placement("notes", width=None, height=None)
        self.assertIsNone(next(p for p in layout.load_layout() if p.id == "notes").width)

    def test_bad_layouts_reject_duplicate_ids_scales_and_unsafe_names(self):
        for entries in ([{"id": "x", "component": "Clock", "width": -1}],
                        [{"id": "x", "component": "Clock", "height": True}],
                        [{"id": "x", "component": "Clock", "width": 20001}],
                        [{"id": "x", "component": "Clock", "height": 12.5}],
                        [{"id": "x", "component": "Clock", "scale": 0}],
                        [{"id": "x", "component": "Clock", "scale": float("nan")}],
                        [{"id": "../x", "component": "Clock"}],
                        [{"id": "x", "component": "Clock", "anchor": "wrong"}],
                        [{"id": "x", "component": "Clock", "props": {"config": {}}}],
                        [{"id": "x", "component": "Clock"}] * 2):
            with self.assertRaises(ValueError):
                layout.parse_layout({"version": 1, "widgets": entries})

    def test_save_one_position_preserves_other_cards_and_user_props(self):
        before = json.loads(Path(storage.LAYOUT).read_text())
        layout.save_placement("clock", anchor="top-left", x=120, y=240, scale=1.4)
        after = json.loads(Path(storage.LAYOUT).read_text())
        self.assertEqual(after["widgets"][1:], before["widgets"][1:])
        self.assertEqual(layout.load_layout()[0].scale, 1.4)
        layout.ensure_layout()
        self.assertEqual(layout.load_layout()[0].x, 120)

    def test_each_widget_toggle_preserves_all_other_widgets(self):
        original = layout.load_layout()
        layout.set_enabled("calendar", False)
        changed = layout.load_layout()
        self.assertFalse(changed[1].enabled)
        self.assertEqual(changed[0], original[0])
        self.assertEqual(changed[2:], original[2:])
        layout.set_enabled("clock", False)
        self.assertTrue(settings.load_config()["clock"])
        self.assertFalse(layout.widget_enabled(layout.load_layout()[0], settings.load_config()))
        self.assertTrue(layout.load_layout()[2].enabled)

    def test_save_note_preserves_geometry_other_props_and_other_widgets(self):
        layout.save_placement("notes", x=145, width=310, enabled=False,
                              props={"title": "Old", "text": "Old text", "custom": "keep"})
        before = json.loads(Path(storage.LAYOUT).read_text())
        layout.save_note("notes", "Shopping 🛒", "Milk\nBread\n\nTea")
        after = json.loads(Path(storage.LAYOUT).read_text())
        for original, changed in zip(before["widgets"], after["widgets"]):
            if original["id"] == "notes":
                self.assertEqual(changed, {**original, "props": {
                    **original["props"], "title": "Shopping 🛒", "text": "Milk\nBread\n\nTea"}})
            else:
                self.assertEqual(changed, original)
        layout.save_note("notes", "", "")
        self.assertEqual(next(p for p in layout.load_layout() if p.id == "notes").props["text"], "")

    def test_save_note_rejects_deleted_or_changed_widget_without_writing(self):
        before = Path(storage.LAYOUT).read_text()
        for widget_id in ("gone", "calendar"):
            with self.assertRaises(ValueError):
                layout.save_note(widget_id, "Title", "Body")
        self.assertEqual(Path(storage.LAYOUT).read_text(), before)

    def test_quick_links_save_preserves_layout_and_rejects_invalid_updates(self):
        layout.save_placement("quick-links", x=123, width=320, props={"custom": "keep"})
        before = json.loads(Path(storage.LAYOUT).read_text())
        layout.save_quick_links("quick-links", "Work", [{"label": "Docs", "url": "example.com/docs"}])
        after = json.loads(Path(storage.LAYOUT).read_text())
        for original, updated in zip(before["widgets"], after["widgets"]):
            expected = {**original, "props": {"custom": "keep", "title": "Work", "links": [
                {"label": "Docs", "url": "https://example.com/docs"}]}} if original["id"] == "quick-links" else original
            self.assertEqual(updated, expected)
        saved = Path(storage.LAYOUT).read_text()
        for widget_id, links in (("gone", []), ("notes", []), ("quick-links", [{"label": "Bad", "url": ""}])):
            with self.assertRaises(ValueError):
                layout.save_quick_links(widget_id, "Title", links)
        self.assertEqual(Path(storage.LAYOUT).read_text(), saved)

    def test_quick_links_upgrade_keeps_custom_placements(self):
        document = json.loads(Path(storage.LAYOUT).read_text())
        document["widgets"] = [item for item in document["widgets"] if item["component"] != "QuickLinks"]
        document["widgets"][0]["x"] = 234
        Path(storage.LAYOUT).write_text(json.dumps(document))
        layout.ensure_layout()
        upgraded = json.loads(Path(storage.LAYOUT).read_text())
        self.assertEqual(upgraded["widgets"][:-1], document["widgets"])
        self.assertEqual(upgraded["widgets"][-1]["component"], "QuickLinks")
        self.assertFalse(upgraded["widgets"][-1]["enabled"])

    def test_custom_component_hot_reload_and_bad_edit_keeps_previous_function(self):
        path = Path(storage.CUSTOM_WIDGETS) / "greeting.py"
        template = 'from trp_strata.components import Text, component\n@component\ndef Widget(config, name="world"):\n    return Text("%s " + name)\n'
        path.write_text(template % "Hello")
        loader = layout.ComponentLoader()
        first = loader.load("greeting")
        self.assertEqual(resolve(first(config={}, name="sel-mlil")).props["text"], "Hello sel-mlil")
        self.assertIs(loader.load("greeting"), first)
        path.write_text(template % "Welcome")
        second = loader.load("greeting")
        self.assertIsNot(first, second)
        path.write_text("invalid python !")
        with self.assertLogs("trp_strata.layout", level="ERROR"):
            self.assertIs(loader.load("greeting"), second)


if __name__ == "__main__":
    unittest.main()
