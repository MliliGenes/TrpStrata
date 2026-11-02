import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from trp_strata.components import Column, Text, Grid, component, resolve
from trp_strata.widget_engine import Controller, Context, Definition, WidgetEngine, handler
from trp_strata.widget_views import definition
from trp_strata.widget_styles import grid_positions, track_sizes


class Loop:
    def __init__(self):
        self.next = 0
        self.idle, self.timers = {}, {}

    def defer(self, callback):
        self.next += 1
        self.idle[self.next] = callback
        return self.next

    def repeat(self, milliseconds, callback):
        self.next += 1
        self.timers[self.next] = callback
        return self.next

    def cancel(self, token):
        self.idle.pop(token, None)
        self.timers.pop(token, None)

    def flush(self):
        pending, self.idle = self.idle, {}
        for callback in pending.values():
            callback()


class Counter(Controller):
    def mount(self, ctx):
        ctx.set_state(count=ctx.props.get("initial", 0))

    @handler
    def increment(self, ctx, event):
        ctx.set_state(count=ctx.state["count"] + 1)


COUNTER = {"controller": "counter", "view": {"type": "Column", "children": [
    {"type": "Text", "text": {"$bind": "state.count"}, "key": "count"},
    {"type": "Button", "text": "+", "events": {"click": "increment"}}]}}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.loop, self.renders = Loop(), []
        self.engine = WidgetEngine(defer=self.loop.defer, repeat=self.loop.repeat,
                                   cancel=self.loop.cancel, on_render=self.renders.append)
        self.addCleanup(self.engine.close)
        self.definition = definition(COUNTER, {"counter": Counter})

    def test_instances_events_and_batched_targeted_updates(self):
        self.engine.mount("a", self.definition, {})
        self.engine.mount("b", self.definition, {"initial": 20})
        a, b = self.engine.render("a"), self.engine.render("b")
        self.loop.flush()
        self.assertEqual(self.renders, [{"a", "b"}])
        a.children[1].props["on_click"]()
        a.children[1].props["on_click"]()
        self.loop.flush()
        self.assertEqual(self.renders[-1], {"a"})
        self.assertEqual(self.engine.render("a").children[0].props["text"], "2")
        self.assertIs(self.engine.render("b"), b)
        with self.assertRaisesRegex(ValueError, "unknown handler"):
            self.engine.dispatch("a", "mount")

    def test_view_reload_keeps_state_and_bad_binding_keeps_tree(self):
        instance = self.engine.mount("a", self.definition, {})
        self.engine.dispatch("a", "increment")
        updated = Definition(Counter, {"type": "Text", "text": {"$bind": "state.count"}, "style": {"fontSize": 30}})
        self.assertIs(self.engine.mount("a", updated, {}), instance)
        tree = self.engine.render("a")
        self.assertEqual(tree.props["text"], "1")
        self.engine.mount("a", Definition(Counter, {"type": "Text", "text": {"$bind": "state.missing"}}), {})
        with self.assertLogs("trp_strata.widget_engine", level="ERROR"):
            self.assertIs(self.engine.render("a"), tree)

    def test_lifecycle_cleans_timers_models_and_ignores_old_events(self):
        closed = []

        class Timed(Counter):
            def mount(self, ctx):
                super().mount(ctx)
                ctx.every(100, lambda: self.increment(ctx, {}))
                ctx.on_cleanup(lambda: closed.append("cleanup"))

            def unmount(self, ctx):
                closed.append("unmount")

        self.engine.mount("a", Definition(Timed, self.definition.view), {})
        button = self.engine.render("a").children[1]
        self.engine.remove("a")
        button.props["on_click"]()
        self.assertEqual(closed, ["unmount", "cleanup"])
        self.assertFalse(self.loop.timers)

    def test_latest_task_wins_and_unmounted_results_are_discarded(self):
        instance = self.engine.mount("a", self.definition, {})
        ctx = Context(self.engine, instance)
        gate, results = threading.Event(), []
        old = ctx.task("load", lambda: (gate.wait(2), "old")[1], results.append)
        new = ctx.task("load", lambda: "new", results.append)
        new.join(2)
        gate.set()
        old.join(2)
        self.loop.flush()
        self.assertEqual(results, ["new"])
        pending = ctx.task("load", lambda: "removed", results.append)
        pending.join(2)
        self.engine.remove("a")
        self.loop.flush()
        self.assertEqual(results, ["new"])

    def test_failed_controller_replacement_keeps_original_instance_alive(self):
        instance = self.engine.mount("a", self.definition, {})
        tree = self.engine.render("a")

        class Broken(Controller):
            def mount(self, ctx):
                ctx.every(100, lambda: None)

        with self.assertRaises(ValueError):
            self.engine.mount("a", Definition(Broken, {"type": "Text", "text": {"$bind": "state.missing"}}), {})
        self.assertIs(self.engine.instances["a"], instance)
        self.assertTrue(instance.alive)
        self.assertFalse(self.loop.timers)
        tree.children[1].props["on_click"]()
        self.assertEqual(instance.state["count"], 1)

    def test_repeat_bindings_dispatch_item_arguments(self):
        class Items(Controller):
            def mount(self, ctx):
                ctx.set_state(items=[{"id": "one", "label": "One"}, {"id": "two", "label": "Two"}])

            @handler
            def choose(self, ctx, event):
                ctx.set_state(selected=event["args"])

        view = {"type": "Grid", "columns": ["1fr", "2fr"], "children": [
            {"repeat": {"$bind": "state.items"}, "key": "id", "template": {
                "type": "Button", "text": {"$bind": "item.label"},
                "events": {"click": {"handler": "choose", "args": {"$bind": "item.id"}}}}}]}
        self.engine.mount("items", definition({"controller": "items", "view": view}, {"items": Items}), {})
        tree = self.engine.render("items")
        self.assertEqual([child.key for child in tree.children], ["one", "two"])
        tree.children[1].props["on_click"]()
        self.assertEqual(self.engine.instances["items"].state["selected"], "two")

    def test_legacy_components_keep_scoped_models_and_targeted_callbacks(self):
        calls = []

        @component
        def Legacy(config):
            from trp_strata.components import Button
            return Button("Click", on_click=lambda: calls.append(1))

        self.engine.mount("legacy", Legacy, {"config": {}})
        tree = self.engine.render("legacy")
        self.loop.flush()
        tree.props["on_click"]()
        self.loop.flush()
        self.assertEqual(calls, [1])
        self.assertEqual(self.renders[-1], {"legacy"})
        self.engine.remove("legacy")
        self.assertFalse(self.loop.timers)


class ViewAndLayoutTests(unittest.TestCase):
    def test_all_builtin_documents_are_valid_and_exportable(self):
        from trp_strata.widget_builtin_views import VIEWS, document
        from trp_strata.widget_controllers import CONTROLLERS
        for name in VIEWS:
            definition(json.loads(json.dumps(document(name))), CONTROLLERS)

    def test_grid_spans_placement_and_content_constrained_fractional_tracks(self):
        tree = resolve(Grid(Text("header", style={"columnSpan": 2}), Text("a"), Text("b"), columns=["1fr", "2fr"]))
        self.assertEqual(grid_positions(tree.children, 2), [(0, 0, 2, 1), (0, 1, 1, 1), (1, 1, 1, 1)])
        self.assertEqual(track_sizes(["1fr", "2fr"], [(0, 1, 10), (1, 1, 10)], 10, 310), [100, 200])
        self.assertEqual(track_sizes(["1fr", "2fr"], [(0, 1, 150)], 10, 310), [150, 150])
        self.assertEqual(track_sizes([40, "auto", "1fr"], [(1, 1, 20)], 5, 170), [40, 20, 100])
        with self.assertRaisesRegex(ValueError, "overlap"):
            resolve(Grid(Text("a", style={"column": 0, "row": 0}), Text("b", style={"column": 0, "row": 0})))

    def test_invalid_styles_and_events_fail_before_mount(self):
        for style in ({"fontSize": -1}, {"columns": ["0fr"]}, {"gap": float("nan")}, {"madeUp": 1}):
            with self.assertRaises(ValueError):
                Text("bad", style=style)
        for view in ({"type": "Text", "events": {"click": "increment"}},
                     {"type": "Button", "events": {"click": "mount"}}):
            with self.assertRaises(ValueError):
                definition({"controller": "counter", "view": view}, {"counter": Counter})

    def test_json_loader_preserves_controller_on_view_edit_and_recovers_from_bad_json(self):
        from trp_strata import layout, storage
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, "CUSTOM_WIDGETS", directory):
            path = Path(directory) / "counter.json"
            module = Path(directory) / "counter.py"
            module.write_text("from trp_strata.widget_engine import Controller as Base, handler\n"
                              "class Controller(Base):\n"
                              "    @handler\n"
                              "    def increment(self, ctx, event): pass\n")
            path.write_text(json.dumps(COUNTER))
            loader = layout.ComponentLoader()
            first = loader.load("counter")
            changed = json.loads(json.dumps(COUNTER))
            changed["view"]["style"] = {"padding": 24}
            path.write_text(json.dumps(changed))
            second = loader.load("counter")
            self.assertIs(first.controller, second.controller)
            self.assertIsNot(first, second)
            path.write_text("{")
            with self.assertLogs("trp_strata.layout", level="ERROR"):
                self.assertIs(loader.load("counter"), second)


if __name__ == "__main__":
    unittest.main()
