"""Native checks for grid tracks, structured styles, event dispatch and view reload."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trp_strata.components import Grid, Text
from trp_strata.gtk_renderer import Renderer
from trp_strata.widget_engine import Controller, Definition, WidgetEngine, handler
from gi.repository import Gtk, GLib, Pango


def settle(window):
    while GLib.MainContext.default().pending():
        GLib.MainContext.default().iteration(False)
    window.check_resize()


def main():
    if not Gtk.init_check()[0]:
        raise SystemExit("A GTK display is required")
    window, renderer = Gtk.OffscreenWindow(), Renderer()
    try:
        tree = Grid(Text("a", key="a", align="fill", style={"fontSize": 30, "textAlign": "end"}),
                    Text("b", key="b", align="fill"), columns=["1fr", "2fr"],
                    style={"width": 360, "height": 120, "padding": 10, "gap": 12})
        window.add(renderer.render(tree))
        window.show_all()
        settle(window)
        a, b = renderer.find("a"), renderer.find("b")
        assert abs(b.get_allocated_width() - 2 * a.get_allocated_width()) <= 2
        assert b.get_allocation().x - (a.get_allocation().x + a.get_allocated_width()) == 12
        assert a.get_xalign() == 1
        font_size = a.get_style_context().get_property("font", Gtk.StateFlags.NORMAL).get_size()
        assert font_size / Pango.SCALE >= 20
        renderer.render(Grid(Text("a", key="a"), Text("b", key="b"), columns=["1fr", "1fr"]))
        settle(window)
        assert renderer.find("a") is a
        assert a.get_xalign() == .5
        assert renderer.root.widget.get_size_request() == (-1, -1)
        assert renderer.root.widget.column_gap == 0
        assert a.get_style_context().get_property("font", Gtk.StateFlags.NORMAL).get_size() < font_size
        previous = renderer.root
        try:
            renderer.render(Text("bad", style={"color": "not-a-color"}))
        except GLib.Error:
            pass
        else:
            raise AssertionError("Invalid GTK CSS must fail before reconciliation")
        assert renderer.root is previous
    finally:
        renderer.close()
        window.destroy()

    class Counter(Controller):
        def mount(self, ctx):
            ctx.set_state(count=0, query="")

        @handler
        def increment(self, ctx, event):
            ctx.set_state(count=ctx.state["count"] + 1)

        @handler
        def search(self, ctx, event):
            ctx.set_state(query=event["value"])

        @handler
        def submit(self, ctx, event):
            ctx.set_state(count=int(event["value"]))

    view = {"type": "Column", "children": [
        {"type": "Text", "text": {"$bind": "state.count"}, "key": "count"},
        {"type": "Button", "text": "Add", "events": {"click": "increment"}, "key": "add"},
        {"type": "Search", "text": {"$bind": "state.query"}, "events": {"change": "search", "submit": "submit"}, "key": "input"}]}
    window, renderer = Gtk.OffscreenWindow(), Renderer()
    engine = WidgetEngine(defer=GLib.idle_add, repeat=GLib.timeout_add, cancel=GLib.source_remove,
                          on_render=lambda ids: renderer.render(engine.render("counter")))
    try:
        instance = engine.mount("counter", Definition(Counter, view), {})
        window.add(renderer.render(engine.render("counter")))
        window.show_all()
        settle(window)
        label = renderer.find("count")
        renderer.find("add").clicked()
        settle(window)
        assert renderer.find("count") is label
        assert label.get_text() == "1"
        updated = {**view, "style": {"padding": 18, "gap": 14}}
        engine.mount("counter", Definition(Counter, updated), {})
        settle(window)
        assert engine.instances["counter"] is instance
        assert label.get_text() == "1"
        assert renderer.root.widget.get_spacing() == 14
        renderer.find("input").set_text("5")
        renderer.find("input").emit("activate")
        settle(window)
        assert label.get_text() == "5"
        engine.remove("counter")
        renderer.find("add").clicked()
        assert not engine.instances
    finally:
        engine.close()
        renderer.close()
        window.destroy()
    print("Widget engine, JSON events, state-preserving reload, grid allocation and style reset: passed")


if __name__ == "__main__":
    main()
