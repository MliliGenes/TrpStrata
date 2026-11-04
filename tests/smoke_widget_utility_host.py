"""Exercise utility CSS, presets, overrides and error recovery through the desktop host."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory() as directory:
        os.environ["XDG_CONFIG_HOME"] = directory
        os.environ["XDG_CACHE_HOME"] = directory
        from trp_strata import core, layout, storage, styles
        from trp_strata.widget_runtime import DesktopWidgets
        from gi.repository import Gtk, Gdk, GLib
        if not Gtk.init_check()[0]:
            raise SystemExit("A GTK display is required")
        Gtk.Settings.get_default().set_property("gtk-enable-animations", False)
        rectangle = Gdk.Rectangle()
        rectangle.x, rectangle.y, rectangle.width, rectangle.height = 0, 0, 1280, 900
        Gdk.Monitor.get_workarea = lambda _monitor: rectangle
        styles.ensure_user_styles()
        folder = Path(storage.CUSTOM_WIDGETS) / "sample"
        folder.mkdir()
        (folder / "view.json").write_text(json.dumps({"view": {"type": "Column", "class_name": "gap-3", "children": [
            {"type": "Text", "text": "Example", "key": "heading",
             "class_name": "text-em-2 font-display text-theme-muted"}]}}))
        Path(storage.LAYOUT).write_text(json.dumps({"version": 1, "removed_defaults": list(layout.AUTO_COMPONENTS),
                                                  "widgets": [{"id": "notes", "component": "Notes"},
                                                              {"id": "sample", "component": "sample"}]}))
        core.save_config(widget_font="mono", layout_grid=False, widget_blur=False)
        host = DesktopWidgets(lambda: False)

        def settle():
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            host.window.check_resize()

        try:
            settle()
            sample = host.frames["sample"].renderer
            heading = sample.find("heading")
            context, state = heading.get_style_context(), Gtk.StateFlags.NORMAL
            assert sample.root.children[0].widget.get_spacing() == 12
            assert host.frames["notes"].renderer.root.children[0].widget.get_spacing() == 10
            assert "Mono" in context.get_font(state).get_family()
            core.save_config(widget_font="serif")
            host.reload()
            settle()
            assert sample.find("heading") is heading
            assert context.get_font(state).get_family().startswith("DejaVu Serif")
            original_size = context.get_font(state).get_size()
            layout.save_placement("sample", scale=1.5, class_name="red")
            host.reload()
            settle()
            assert abs(context.get_font(state).get_size() / original_size - 1.5) < .01
            assert abs(context.get_color(state).alpha - .76) < .001
            Path(core.WIDGETS_CSS).write_text(".text-theme-muted { color: #123456; } .font-display { font-size: 30px; }")
            host.reload()
            settle()
            assert abs(context.get_color(state).red - 0x12 / 255) < .001
            custom_size = context.get_font(state).get_size()
            Path(core.WIDGETS_CSS).write_text(".broken { invalid-css }")
            with unittest.TestCase().assertLogs("trp_strata.widget_runtime", level="WARNING"):
                host.reload()
            settle()
            assert abs(context.get_color(state).red - 0x12 / 255) < .001
            assert context.get_font(state).get_size() == custom_size
            Path(core.WIDGETS_CSS).write_text("")
            host.reload()
            settle()
            assert abs(context.get_color(state).alpha - .76) < .001
        finally:
            host.close()
    print("Utility desktop host: migrated Notes, preset/scale changes, red contrast, CSS overrides and invalid-edit recovery passed")


if __name__ == "__main__":
    main()
