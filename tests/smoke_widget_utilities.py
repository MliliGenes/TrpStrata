"""Check utilities against real GTK CSS, layout, palette changes and class removal."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trp_strata.components import Column, Grid, Text
from trp_strata.gtk_renderer import Renderer
from trp_strata.gtk_widget_styles import provider_for
from trp_strata.widget_styles import css
from trp_strata.widget_utilities import UTILITIES, stylesheet
from gi.repository import Gtk, Gdk, GLib, Pango


def settle(window):
    while GLib.MainContext.default().pending():
        GLib.MainContext.default().iteration(False)
    window.check_resize()


def main():
    if not Gtk.init_check()[0]:
        raise SystemExit("A GTK display is required")
    screen = Gdk.Screen.get_default()
    palette = Gtk.CssProvider()
    names = set(re.findall(r"@(ws_[a-z_]+)", stylesheet()))
    palette.load_from_data(("".join(f"@define-color {name} #123456;" for name in names)
                            + ".legacy { font-size: 10px; color: #ffffff; }").encode())
    Gtk.StyleContext.add_provider_for_screen(screen, palette, Gtk.STYLE_PROVIDER_PRIORITY_USER + 2)
    window, renderer = Gtk.OffscreenWindow(), Renderer()
    try:
        for name, style in UTILITIES.items():
            try:
                provider_for(css(style))
            except GLib.Error as error:
                raise AssertionError(f"Utility {name} generated invalid GTK CSS") from error
        tree = Column(Text("Heading", key="heading", class_name="legacy u:text-2xl font-bold text-accent self-start text-right text-wrap grow"),
                      class_name="p-4 gap-3 w-64 rounded-xl border border-muted bg-surface")
        window.add(renderer.render(tree))
        window.show_all()
        settle(window)
        root, heading = renderer.root.widget, renderer.find("heading")
        style, state = root.get_style_context(), Gtk.StateFlags.NORMAL
        padding = style.get_padding(state)
        assert (padding.top, padding.right, padding.bottom, padding.left) == (16, 16, 16, 16)
        assert style.get_border(state).top == 1
        assert root.get_spacing() == 12
        assert root.get_size_request() == (256, -1)
        assert heading.get_halign() == Gtk.Align.START
        assert heading.get_xalign() == 1
        assert heading.get_line_wrap()
        assert heading.get_hexpand()
        context = heading.get_style_context()
        font_size = context.get_property("font", state).get_size() / Pango.SCALE
        assert font_size >= 18, font_size
        assert abs(context.get_color(state).red - 0x12 / 255) < .001
        # Palette tokens stay symbolic even when their structured CSS is cached.
        palette.load_from_data(("".join(f"@define-color {name} #abcdef;" for name in names)
                                + ".legacy { font-size: 10px; }").encode())
        settle(window)
        assert abs(context.get_color(state).red - 0xab / 255) < .001
        renderer.render(Column(Text("Heading", key="heading", class_name="legacy text-sm", style={"fontSize": 18}),
                               class_name="gap-4", style={"gap": 7}))
        settle(window)
        assert renderer.find("heading") is heading
        assert context.get_property("font", state).get_size() / Pango.SCALE < font_size
        assert root.get_spacing() == 7
        renderer.render(Column(Text("Heading", key="heading", class_name="legacy")))
        settle(window)
        assert root.get_spacing() == 0
        assert root.get_size_request() == (-1, -1)
        assert root.get_style_context().get_padding(state).left == 0
        assert context.get_property("font", state).get_size() / Pango.SCALE < 10
        assert heading.get_halign() == Gtk.Align.CENTER
        assert heading.get_xalign() == .5
        assert not heading.get_line_wrap()
        assert not heading.get_hexpand()
        for classes in ("p-4 px-2", "px-2 p-4"):
            renderer.render(Column(Text("Heading", key="heading", class_name="legacy"), class_name=classes))
            settle(window)
            padding = root.get_style_context().get_padding(state)
            assert (padding.top, padding.right, padding.bottom, padding.left) == (16, 8, 16, 8)
        window.remove(root)
        tree = Grid(Text("A", key="a", align="fill"), Text("B", key="b", align="fill"),
                    Text("Wide", key="wide", class_name="col-span-2"),
                    class_name="grid-cols-2 gap-3 w-64")
        window.add(renderer.render(tree))
        settle(window)
        a, b = renderer.find("a"), renderer.find("b")
        assert abs(a.get_allocated_width() - b.get_allocated_width()) <= 1
        assert b.get_allocation().x - (a.get_allocation().x + a.get_allocated_width()) == 12
        assert renderer.root.widget.column_gap == renderer.root.widget.row_gap == 12
    finally:
        renderer.close()
        window.destroy()
        Gtk.StyleContext.remove_provider_for_screen(screen, palette)
    print("Widget utilities: GTK CSS, spacing, typography, palette changes, grid, precedence and removal passed")


if __name__ == "__main__":
    main()
