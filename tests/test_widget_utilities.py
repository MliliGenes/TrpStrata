import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from datetime import date

from trp_strata.components import Column, Grid, Row, Text, resolve
from trp_strata.widget_engine import Controller, Definition, WidgetEngine
from trp_strata.widget_styles import LAYOUT, css, grid_positions, validate
from trp_strata.widget_utilities import (
    UTILITIES, CSS_UTILITIES, _css_registry, stylesheet, resolve_style, utility_style, css_classes)
from trp_strata.widget_views import definition, build_view


class UtilityTests(unittest.TestCase):
    def engine(self):
        engine = WidgetEngine(defer=lambda callback: 1, repeat=lambda ms, callback: 1,
                              cancel=lambda token: None, on_render=lambda ids: None)
        self.addCleanup(engine.close)
        return engine

    def test_every_registered_utility_is_a_valid_native_style(self):
        for name, style in UTILITIES.items():
            with self.subTest(name=name):
                self.assertEqual(utility_style(name), validate(style))
                css(style)

    def test_stylesheet_is_the_source_of_visual_class_definitions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "widgets.css"
            path.write_text("/* BEGIN WIDGET UTILITY CATALOGUE */\n.text-test { font-size: 22px; }\n"
                            "/* END WIDGET UTILITY CATALOGUE */")
            with patch("trp_strata.widget_utilities.STYLESHEET", path):
                self.assertEqual(_css_registry(), {"text-test": {"fontSize": 22}})
        self.assertEqual(css_classes("u:p-4 u:text-em-0.72 my-card"), {"p-4", "text-em-0.72", "my-card"})
        self.assertTrue(CSS_UTILITIES)
        for name, style in CSS_UTILITIES.items():
            self.assertFalse(set(style) & LAYOUT, name)
        # Even non-CSS layout class names have a reference entry in the stylesheet.
        for name in set(UTILITIES) - set(CSS_UTILITIES):
            self.assertTrue(name in stylesheet(), name)

    def test_relative_sizes_and_theme_aware_colour_classes_are_defined(self):
        self.assertEqual(utility_style("text-em-0.72 px-em-0.25 tracking-tight"),
                         {"fontSize": "0.72em", "paddingLeft": "0.25em", "paddingRight": "0.25em",
                          "letterSpacing": "-0.02em"})
        self.assertIn(".desktop-widget.red .text-theme-muted", stylesheet())

    def test_relative_css_lengths_do_not_relax_native_layout_validation(self):
        self.assertEqual(validate({"fontSize": "1.2em", "letterSpacing": "-0.02em"}),
                         {"fontSize": "1.2em", "letterSpacing": "-0.02em"})
        for style in ({"width": "2em"}, {"gap": "1em"}, {"padding": "-1em"},
                      {"fontSize": "nanem"}, {"fontSize": "1em; color:red"}):
            with self.subTest(style=style), self.assertRaises(ValueError):
                validate(style)

    def test_all_builtin_views_use_utilities_without_inline_layout_fields(self):
        from trp_strata.widget_packages import DIRECTORY, PACKAGES

        def check_classes(value):
            if isinstance(value, str):
                for token in value.split():
                    self.assertIn(token, UTILITIES)
                    self.assertFalse(token.startswith("text-theme-"), token)
            elif isinstance(value, list):
                for fragment in value:
                    check_classes(fragment)
            else:
                self.assertIsInstance(value, dict)
                self.assertNotIn("$bind", value, "Built-ins must not obtain class names from controller data")
                for names in value:
                    check_classes(names)

        def check(node):
            if "repeat" in node:
                check(node["template"])
                return
            for field in ("spacing", "align", "expand", "wrap", "columns", "style"):
                self.assertNotIn(field, node)
            classes = node.get("class_name", "")
            check_classes(classes)
            static = " ".join(value for value in classes if isinstance(value, str)) if isinstance(classes, list) else classes
            self.assertIsInstance(static, str)
            if node["type"] in ("Column", "Row", "Grid"):
                self.assertIn("gap", utility_style(static))
            for child in node.get("children", []):
                check(child)
        for folder, _alias in PACKAGES.values():
            with self.subTest(widget=folder):
                check(json.loads((DIRECTORY / folder / "view.json").read_text())["view"])

    def test_state_theme_and_subnode_classes_are_real_css_utilities(self):
        names = ("bg-primary/5.5", "hover:bg-accent-soft", "active:border-accent-strong",
                 "red:disabled:text-on-accent/55", "light:focus:border-accent", "label:text-em-0.84",
                 "trough:min-h-em-0.35", "red:progress:bg-on-accent")
        for name in names:
            with self.subTest(name=name):
                self.assertIn(name, CSS_UTILITIES)
                self.assertEqual(utility_style("u:" + name), CSS_UTILITIES[name])
        # Ancestor/state overrides must not replace metadata for plain palette classes.
        self.assertEqual(CSS_UTILITIES["text-primary"], {"color": "@ws_ink"})

    def test_conditional_classes_require_booleans_and_retain_last_good_tree(self):
        engine = self.engine()
        view = {"type": "Text", "class_name": ["text-sm", {"grow font-bold": {"$bind": "props.enabled"}}]}
        document = definition({"view": view}, {"static": Controller})
        instance = engine.mount("test", document, {"enabled": True})
        tree = engine.render("test")
        self.assertEqual(tree.props["class_name"], "text-sm grow font-bold")
        instance.props["enabled"] = "false"
        engine.invalidate("test")
        with self.assertLogs("trp_strata.widget_engine", level="ERROR"):
            self.assertIs(engine.render("test"), tree)
        instance.props["enabled"] = False
        engine.invalidate("test")
        updated = engine.render("test")
        self.assertEqual(updated.props["class_name"].strip(), "text-sm")
        self.assertNotIn("expand", updated.props["style"])
        for classes in ({"u:no-such-class": False}, {"grow": "yes"}, {"grow": {"$bind": 1}}):
            with self.subTest(classes=classes), self.assertRaises(ValueError):
                definition({"view": {"type": "Text", "class_name": classes}}, {"static": Controller})

    def test_calendar_states_render_only_utility_classes(self):
        from trp_strata.widget_packages.calendar.controller import Controller as Calendar
        state = {}
        with patch("trp_strata.widget_packages.calendar.controller.date") as clock:
            clock.today.return_value = date(2026, 11, 4)
            Calendar().refresh(SimpleNamespace(set_state=lambda **values: state.update(values)))
        path = Path(__file__).resolve().parents[1] / "trp_strata/widget_packages/calendar/view.json"
        tree = resolve(build_view(json.loads(path.read_text())["view"], SimpleNamespace(state=state, props={})))
        cells = tree.children[2].children
        self.assertEqual(sum(cell["weekday"] for cell in state["cells"]), 7)
        self.assertEqual(sum(cell["today"] for cell in state["cells"]), 1)
        highlighted = [cell for cell in cells if "bg-accent/14" in cell.props["class_name"].split()]
        self.assertEqual(len(highlighted), 1)
        self.assertEqual(highlighted[0].props["text"], "4")
        for cell in cells:
            self.assertTrue(set(cell.props["class_name"].split()) <= UTILITIES.keys())

    def test_class_fragments_combine_static_utilities_and_bindings(self):
        engine = self.engine()
        view = {"type": "Text", "class_name": ["p-4 grow", {"$bind": "props.classes"}]}
        document = definition({"view": view}, {"static": Controller})
        engine.mount("test", document, {"classes": "my-state text-em-0.72"})
        tree = engine.render("test")
        self.assertEqual(tree.props["class_name"], "p-4 grow my-state text-em-0.72")
        self.assertEqual(tree.props["style"], {"expand": True})
        with self.assertRaisesRegex(ValueError, "class_name"):
            definition({"view": {"type": "Text", "class_name": ["u:p-999"]}}, {"static": Controller})

    def test_spacing_scale_and_directional_edges(self):
        style = utility_style("p-4 px-2 pt-px m-0.5 mb-2.5")
        self.assertEqual(style, {"paddingTop": 1, "paddingRight": 8,
                                "paddingBottom": 16, "paddingLeft": 8,
                                "marginTop": 2, "marginRight": 2,
                                "marginBottom": 10, "marginLeft": 2})
        self.assertEqual(utility_style("px-2 p-4")["paddingLeft"], 16)

    def test_gap_conflicts_are_resolved_left_to_right(self):
        self.assertEqual(utility_style("gap-3 gap-x-1"), {"gap": 12, "rowGap": 12, "columnGap": 4})
        self.assertEqual(utility_style("gap-x-1 gap-3"), {"gap": 12, "rowGap": 12, "columnGap": 12})

    def test_palette_typography_borders_and_shadows(self):
        style = utility_style("text-2xl font-bold text-accent bg-surface rounded-xl border border-muted shadow-sm")
        self.assertEqual(style["fontSize"], 24)
        self.assertEqual(style["fontWeight"], 700)
        self.assertEqual(style["color"], "@ws_accent")
        self.assertEqual(style["background"], "@ws_sheet")
        self.assertEqual(style["borderRadius"], 12)
        self.assertEqual(style["borderWidth"], 1)
        self.assertEqual(style["borderColor"], "@ws_muted")
        self.assertIn("@ws_shadow", style["boxShadow"])

    def test_class_order_and_explicit_styles_override_defaults(self):
        element = Row(spacing=5, class_name="gap-4 gap-2 w-32 grow", style={"gap": 7, "width": 200, "expand": False})
        self.assertEqual(element.props["spacing"], 5)
        self.assertEqual(element.props["style"], {"gap": 7, "rowGap": 7, "columnGap": 7,
                                                  "width": 200, "expand": False})
        # Appearance stays in the native stylesheet rather than high-priority inline CSS.
        self.assertEqual(Text(class_name="text-sm text-xl").props["style"], {})

    def test_inline_shorthands_override_utility_edges(self):
        style = resolve_style("p-8 mx-4 gap-y-5", {"padding": [1, 2, 3, 4], "paddingLeft": 9,
                                                  "margin": 0, "gap": 2, "columnGap": 7})
        self.assertEqual([style["padding" + edge] for edge in ("Top", "Right", "Bottom", "Left")], [1, 2, 3, 9])
        self.assertEqual(style["marginLeft"], 0)
        self.assertEqual(style["marginRight"], 0)
        self.assertEqual((style["gap"], style["rowGap"], style["columnGap"]), (2, 2, 7))

    def test_custom_classes_and_existing_styles_are_preserved(self):
        element = Text(class_name="clock-hours my-custom-class text-custom", style={"padding": [1, 2]})
        self.assertEqual(element.props["class_name"], "clock-hours my-custom-class text-custom")
        self.assertEqual(element.props["style"], {"padding": [1, 2]})
        self.assertEqual(utility_style("my-card\n\tp-4   text-sm"), utility_style("p-4 text-sm"))

    def test_resolved_track_lists_cannot_mutate_the_registry(self):
        first = utility_style("grid-cols-2")
        first["columns"].append("2fr")
        self.assertEqual(utility_style("grid-cols-2")["columns"], ["1fr", "1fr"])

    def test_layout_classes_accept_fractional_and_strict_utilities(self):
        from trp_strata.layout import parse_layout
        entry = {"id": "notes", "component": "Notes", "class_name": "my-card p-2.5 u:rounded-xl bg-surface"}
        placement, = parse_layout({"version": 1, "widgets": [entry]})
        self.assertEqual(placement.class_name, entry["class_name"])
        for classes in ("u:p-999", "p-[13px]", "bad;class", "my.custom"):
            with self.subTest(classes=classes), self.assertRaises(ValueError):
                parse_layout({"version": 1, "widgets": [{**entry, "class_name": classes}]})

    def test_strict_utilities_report_typos_and_unsupported_features(self):
        self.assertEqual(utility_style("u:p-4 u:text-sm"), utility_style("p-4 text-sm"))
        with self.assertRaisesRegex(ValueError, "did you mean u:rounded-xl"):
            Text(class_name="u:rounded-xll")
        for classes in ("u:p-[13px]", "u:sm:hover:bg-accent", "u:w-full", "u:-m-2", "u:"):
            with self.subTest(classes=classes), self.assertRaisesRegex(ValueError, "Unknown widget utility"):
                Text(class_name=classes)
        for classes in (None, [], 42):
            with self.assertRaises(TypeError):
                utility_style(classes)

    def test_grid_tracks_spans_and_one_based_placement(self):
        tree = resolve(Grid(Text("Heading", class_name="col-span-2"),
                            Text("End", class_name="col-start-2 row-start-2"),
                            class_name="grid-cols-2 grid-rows-2 gap-3"))
        self.assertEqual(tree.props["style"]["columns"], ["1fr", "1fr"])
        self.assertEqual(grid_positions(tree.children, 2), [(0, 0, 2, 1), (1, 1, 1, 1)])
        with self.assertRaisesRegex(ValueError, "exceeds"):
            resolve(Grid(Text(class_name="col-span-3"), class_name="grid-cols-2"))

    def test_sizing_alignment_and_wrapping(self):
        style = utility_style("size-8 w-16 min-h-4 self-start vself-end text-right text-wrap grow vgrow")
        self.assertEqual(style, {"width": 64, "height": 32, "minHeight": 16, "alignSelf": "start",
                                "valignSelf": "end", "textAlign": "end", "wrap": True,
                                "expand": True, "vexpand": True})

    def test_json_static_classes_are_validated_with_the_node_path(self):
        for classes in ("u:p-999", 5):
            with self.assertRaisesRegex(ValueError, r"view.children\[0\].class_name"):
                definition({"view": {"type": "Column", "children": [{"type": "Text", "class_name": classes}]}},
                           {"static": Controller})

    def test_bound_classes_and_view_reload_keep_controller_state(self):
        class Styled(Controller):
            def mount(self, ctx):
                ctx.set_state(classes="p-2 text-sm", count=4)

        engine = self.engine()
        view = {"type": "Text", "class_name": {"$bind": "state.classes"}, "text": {"$bind": "state.count"}}
        document = definition({"controller": "styled", "view": view}, {"styled": Styled})
        instance = engine.mount("test", document, {})
        first = engine.render("test")
        self.assertEqual(utility_style(first.props["class_name"])["fontSize"], 14)
        # A view-only change preserves the controller and its state.
        changed = {**view, "class_name": "text-2xl text-accent"}
        self.assertIs(engine.mount("test", Definition(Styled, changed), {}), instance)
        second = engine.render("test")
        self.assertEqual(second.props["text"], "4")
        self.assertEqual(utility_style(second.props["class_name"]), {"fontSize": 24, "color": "@ws_accent"})
        self.assertEqual(second.props["style"], {})
        self.assertNotIn("paddingTop", second.props["style"])

    def test_bad_bound_utility_retains_last_good_tree(self):
        engine = self.engine()
        view = {"type": "Text", "class_name": {"$bind": "props.classes"}}
        instance = engine.mount("test", Definition(Controller, view), {"classes": "u:p-4"})
        first = engine.render("test")
        instance.props["classes"] = "u:p-999"
        engine.invalidate("test")
        with self.assertLogs("trp_strata.widget_engine", level="ERROR"):
            self.assertIs(engine.render("test"), first)

    def test_builtin_notes_uses_utilities_without_changing_layout(self):
        path = Path(__file__).resolve().parents[1] / "trp_strata/widget_packages/notes/view.json"
        view = json.loads(path.read_text())["view"]
        self.assertEqual(utility_style(view["class_name"])["gap"], 10)
        for child in view["children"]:
            style = utility_style(child["class_name"])
            self.assertEqual(style["alignSelf"], "start")
            self.assertEqual(style["textAlign"], "start")

    def test_no_gtk_dependency(self):
        result = subprocess.run([sys.executable, "-c",
                                 "from trp_strata.components import Text; "
                                 "Text(class_name='p-4 text-accent'); "
                                 "import sys; assert 'gi' not in sys.modules"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
