"""Compare every built-in's utility styling with its legacy CSS hooks in real GTK."""
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trp_strata.components import Column
from trp_strata.gtk_renderer import Renderer
from trp_strata import widget_fonts
from trp_strata.widget_utilities import STYLESHEET, START, END, stylesheet, utility_style
from trp_strata.widget_styles import LAYOUT
from trp_strata.widget_views import build_view
from gi.repository import Gdk, Gtk, GLib


STATE = dict(title="Example", level="50%", value=50, label="Level", available=True,
             mute_label="Mute", show_mute=True, error="", show_error=False,
             month="November", day="04", enabled=True, status="Ready", hours="12",
             minutes="30", date="Wednesday", visible=True, show_date=True, can_refresh=True,
             query="", show_hint=True, show_pages=True, can_previous=True, can_next=True,
             login="example", fraction=.5, percent="50%", period="This month", refresh_label="Refresh",
             text="Example notes\nSecond line", artwork=None, artist="Artist", show_artist=True,
             album="Album", show_album=True, show_status=True,
             cells=[{"id": "weekday", "text": "Mo", "class": "calendar-weekday", "weekday": True, "ordinary": False, "today": False},
                    {"id": "day", "text": "3", "class": "calendar-cell", "weekday": False, "ordinary": True, "today": False},
                    {"id": "today", "text": "4", "class": "calendar-cell today", "weekday": False, "ordinary": False, "today": True}],
             results=[{"id": "/example", "name": "Example", "icon": "text-x-generic", "directory": "/home/example"}],
             apps=[{"id": "app", "name": "App", "icon": "application-x-executable", "tooltip": "App"}],
             controls=[{"id": "play", "label": "Play", "icon": "play", "enabled": True}],
             links=[{"id": "link", "label": "Example", "url": "https://example.com", "icon": "web-browser"}],
             metrics=[{"id": "CPU", "text": "50%", "value": .5, "available": True}])


def settle(window):
    while GLib.MainContext.default().pending():
        GLib.MainContext.default().iteration(False)
    window.check_resize()


def legacy_view(node, hooks, path=""):
    """Reconstruct the frozen pre-migration hooks, keeping native layout equivalent."""
    if "repeat" in node:
        return {**node, "template": legacy_view(node["template"], hooks, path + "/template")}
    classes = node.get("class_name", "")
    static = " ".join(value for value in classes if isinstance(value, str)) if isinstance(classes, list) else classes
    style = {key: value for key, value in utility_style(static).items() if key in LAYOUT}
    return {**node, "class_name": hooks.get(path, ""), "style": style,
            **({"children": [legacy_view(child, hooks, path + f"/{index}")
                              for index, child in enumerate(node["children"])]} if "children" in node else {})}


def button_states(mounted, flags):
    if mounted.element.kind == "button":
        mounted.widget.set_sensitive(flags != Gtk.StateFlags.INSENSITIVE)
        mounted.widget.set_state_flags(flags, True)
    for child in mounted.children:
        button_states(child, flags)


def snapshot(mounted):
    result = []

    def css_values(context, state):
        color = context.get_color(state)
        background = context.get_background_color(state)
        border_color = context.get_border_color(state)
        padding, border = context.get_padding(state), context.get_border(state)
        edges = (border.top, border.right, border.bottom, border.left)
        return (context.get_font(state).to_string(),
                tuple(round(value, 5) for value in (color.red, color.green, color.blue, color.alpha)),
                tuple(round(value, 5) for value in (background.red, background.green, background.blue, background.alpha)),
                tuple(round(value, 5) for value in (border_color.red, border_color.green, border_color.blue, border_color.alpha)) if any(edges) else None,
                (padding.top, padding.right, padding.bottom, padding.left), edges,
                context.get_property("min-width", state), context.get_property("min-height", state))

    def record(widget, kind):
        result.append((kind, *css_values(widget.get_style_context(), widget.get_state_flags()),
                       # Drawing-area requests are refreshed lazily by style-updated.
                       None if isinstance(widget, Gtk.DrawingArea) else tuple(widget.get_size_request()),
                       widget.get_halign(), widget.get_valign(),
                       widget.get_hexpand(), widget.get_vexpand()))

    def internal(widget):
        record(widget, "button/" + type(widget).__name__)
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                internal(child)

    def walk(node):
        widget = node.widget
        record(widget, node.element.kind)
        if node.element.kind == "button":
            internal(widget.get_child())
        if node.element.kind == "progress":
            # These are CSS subnodes, not GtkWidgets. Build their real native
            # style paths so trough/fill properties are covered as well.
            parent = widget.get_style_context()
            for name in ("trough", "progress"):
                path = parent.get_path().copy()
                index = path.append_type(Gtk.Widget)
                path.iter_set_object_name(index, name)
                context = Gtk.StyleContext()
                context.set_screen(widget.get_screen())
                context.set_path(path)
                context.set_parent(parent)
                context.set_state(widget.get_state_flags())
                result.append(("progress/" + name, *css_values(context, widget.get_state_flags())))
                parent = context
        for child in node.children:
            walk(child)
    walk(mounted)
    return result


def main():
    if not Gtk.init_check()[0]:
        raise SystemExit("A GTK display is required")
    Gtk.Settings.get_default().set_property("gtk-enable-animations", False)
    widget_fonts.register()
    screen = Gdk.Screen.get_default()
    source = STYLESHEET.read_text()
    base_css = source.split(START)[0] + source.split(END)[1]
    names = set(re.findall(r"@((?:ws_)[a-z_]+)", source))
    colors = "".join(f"@define-color {name} #789abc;" for name in names)
    colors += "@define-color ws_ink #f4f5f7; @define-color ws_muted #bac0ce; @define-color ws_on_accent #111827;"
    window, renderer = Gtk.OffscreenWindow(), Renderer()
    window.set_name("ws-desktop-widgets")
    base, utilities = Gtk.CssProvider(), Gtk.CssProvider()
    Gtk.StyleContext.add_provider_for_screen(screen, base, Gtk.STYLE_PROVIDER_PRIORITY_USER + 2)
    Gtk.StyleContext.add_provider_for_screen(screen, utilities, Gtk.STYLE_PROVIDER_PRIORITY_USER + 3)
    packages = sorted(STYLESHEET.parent.parent.joinpath("widget_packages").glob("*/view.json"))
    hooks = json.loads(Path(__file__).with_name("fixtures").joinpath("widget_class_hooks.json").read_text())
    comparisons = 0
    try:
        for preset in widget_fonts.PRESETS:
            for scale in (1, 1.5):
                base.load_from_data((colors + base_css + widget_fonts.css(preset)
                                     + f"#widget-migration {{ font-size: {14 * scale}px; }}").encode())
                utilities.load_from_data((stylesheet() + widget_fonts.utility_css(preset)).encode())
                for variant in ("", "red", "light", "glass", "transparent"):
                    for path in packages:
                        view = json.loads(path.read_text())["view"]
                        ctx = SimpleNamespace(state=STATE, props={})
                        tree = build_view(view, ctx)
                        modern = Column(tree, class_name=f"desktop-widget {variant}")
                        old = Column(build_view(legacy_view(view, hooks[path.parent.name]), ctx), class_name=f"desktop-widget {variant}")
                        flags = [Gtk.StateFlags.NORMAL]
                        if preset == "sans" and scale == 1:
                            flags += [Gtk.StateFlags.PRELIGHT, Gtk.StateFlags.ACTIVE, Gtk.StateFlags.FOCUSED,
                                      Gtk.StateFlags.INSENSITIVE, Gtk.StateFlags.PRELIGHT | Gtk.StateFlags.ACTIVE]
                        for flag in flags:
                            for candidate in (modern, old):
                                widget = renderer.render(candidate)
                                widget.set_name("widget-migration")
                                if widget.get_parent() is None:
                                    window.add(widget)
                                button_states(renderer.root, flag)
                                window.show_all()
                                settle(window)
                                if candidate is modern:
                                    expected = snapshot(renderer.root)
                                else:
                                    actual = snapshot(renderer.root)
                                    for index, (a, b) in enumerate(zip(expected, actual)):
                                        assert a == b, (path.parent.name, preset, scale, variant, flag, index, a, b)
                                    assert len(expected) == len(actual)
                            comparisons += 1
    finally:
        renderer.close()
        window.destroy()
        for provider in (base, utilities):
            Gtk.StyleContext.remove_provider_for_screen(screen, provider)
    print(f"Built-in utility migration: {comparisons} legacy appearance comparisons passed (all 12 widgets, fonts, scales and variants)")


if __name__ == "__main__":
    main()
