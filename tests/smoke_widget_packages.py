"""Exercise real package file notifications, controller events and reload lifecycle."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory() as directory:
        os.environ["XDG_CONFIG_HOME"] = directory
        os.environ["XDG_CACHE_HOME"] = directory
        from trp_strata import storage, styles, layout
        from trp_strata.widget_runtime import DesktopWidgets
        from gi.repository import Gdk, Gtk, GLib
        if not Gtk.init_check()[0]:
            raise SystemExit("A GTK display is required")
        rectangle = Gdk.Rectangle()
        rectangle.x, rectangle.y, rectangle.width, rectangle.height = 0, 0, 1280, 900
        Gdk.Monitor.get_workarea = lambda _monitor: rectangle
        styles.ensure_user_styles()
        folder = Path(storage.CUSTOM_WIDGETS) / "counter"
        folder.mkdir()
        source = (
            "from trp_strata.widget_engine import Controller as Base, handler\n"
            "class Controller(Base):\n"
            "    def mount(self, ctx): ctx.set_state(count=0)\n"
            "    @handler\n"
            "    def increment(self, ctx, event): ctx.set_state(count=ctx.state['count'] + STEP)\n")
        (folder / "controller.py").write_text(source.replace("STEP", "1"))
        view = {"view": {"type": "Column", "children": [
            {"type": "Text", "text": {"$bind": "state.count"}, "key": "count"},
            {"type": "Button", "text": "+", "events": {"click": "increment"}, "key": "add"}]}}
        (folder / "view.json").write_text(json.dumps(view))
        Path(storage.LAYOUT).write_text(json.dumps({"version": 1, "widgets": [
            {"id": "a", "component": "counter"}, {"id": "b", "component": "counter"},
            {"id": "clock", "component": "Clock"}]}))
        host = DesktopWidgets(lambda: False)

        def wait_for(predicate):
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                while GLib.MainContext.default().pending():
                    GLib.MainContext.default().iteration(False)
                host.window.check_resize()
                if predicate():
                    return
                time.sleep(.01)
            raise AssertionError("Timed out waiting for package reload")

        try:
            wait_for(lambda: host.frames["a"].renderer.find("count") is not None)
            renderer = host.frames["a"].renderer
            renderer.find("add").clicked()
            wait_for(lambda: renderer.find("count").get_text() == "1")
            assert host.frames["b"].renderer.find("count").get_text() == "0"
            instance = host.engine.instances["a"]
            view["view"]["style"] = {"gap": 42}
            # Atomic replacement is how many editors save files.
            temporary = folder / "view.tmp"
            temporary.write_text(json.dumps(view))
            temporary.replace(folder / "view.json")
            wait_for(lambda: renderer.root.children[0].widget.get_spacing() == 42)
            assert host.engine.instances["a"] is instance
            assert renderer.find("count").get_text() == "1"
            (folder / "controller.py").write_text(source.replace("STEP", "10"))
            wait_for(lambda: host.engine.instances["a"] is not instance)
            assert not instance.alive
            renderer.find("add").clicked()
            wait_for(lambda: renderer.find("count").get_text() == "10")
            override = Path(storage.CUSTOM_WIDGETS) / "Clock"
            override.mkdir()
            (override / "view.json").write_text(json.dumps({"view": {"type": "Text", "text": "Override", "key": "override"}}))
            wait_for(lambda: host.frames["clock"].renderer.find("override") is not None)
            override.rename(Path(directory) / "removed-clock")
            wait_for(lambda: host.frames["clock"].renderer.find("time") is not None)
            assert override not in host.module_monitor.monitors
            layout.add_widget("counter", "third")
            host.reload()
            wait_for(lambda: "third" in host.engine.instances)
            third = host.engine.instances["third"]
            layout.remove_widget("third")
            host.reload()
            assert "third" not in host.frames and "third" not in host.engine.instances
            assert not third.alive
            assert (folder / "controller.py").exists()
        finally:
            host.close()
        assert not host.module_monitor.monitors
        print("Widget packages: events, independent state, atomic view saves, controller replacement, creation/removal and watcher cleanup passed")


if __name__ == "__main__":
    main()
