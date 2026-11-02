"""Translate component elements to GTK 3, reusing widgets between renders."""
from dataclasses import dataclass, field
import math

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango, PangoCairo  # noqa: E402

from .components import resolve  # noqa: E402
from .gtk_icons import SvgIcon  # noqa: E402
from .gtk_app_icons import AppIcon  # noqa: E402
from .gtk_grid import Grid  # noqa: E402
from .gtk_widget_styles import apply as apply_style, validate_tree  # noqa: E402
from .widget_styles import grid_positions  # noqa: E402


@dataclass
class Mounted:
    element: object
    widget: object
    children: list = field(default_factory=list)

    @property
    def visible(self):
        if not self.element.props["visible"]:
            return False
        return any(child.visible for child in self.children) if self.children else True


class Renderer:
    """Render props into native GTK widgets. Use only on the GTK main thread."""
    def __init__(self, on_action=None):
        self.root = None
        self.on_action = on_action
        self.interactive = True

    def click(self, mounted):
        if self.interactive:
            mounted.element.props["on_click"]()
            if self.on_action is not None:
                self.on_action()

    def search_changed(self, mounted):
        if self.interactive and not mounted.widget.updating:
            mounted.element.props["on_change"](mounted.widget.get_text())
            if self.on_action is not None:
                self.on_action()

    def slider_changed(self, mounted):
        if self.interactive and not mounted.widget.updating:
            mounted.element.props["on_change"](round(mounted.widget.get_value()))
            if self.on_action is not None:
                self.on_action()

    @staticmethod
    def focus_search(widget, event):
        # Desktop cards normally avoid focus; typing is an explicit exception.
        window = widget.get_toplevel()
        if isinstance(window, Gtk.Window):
            window.set_accept_focus(True)
            window.present_with_time(event.time)
            widget.grab_focus()
        return False

    def search_submitted(self, mounted):
        callback = mounted.element.props.get("on_submit")
        if self.interactive and callback is not None:
            callback(mounted.widget.get_text())
            if self.on_action is not None:
                self.on_action()

    @staticmethod
    def size_ring(area):
        # GtkDrawingArea does not include CSS minimum dimensions in its preferred size.
        style = area.get_style_context()
        width = max(1, style.get_property("min-width", Gtk.StateFlags.NORMAL))
        height = max(1, style.get_property("min-height", Gtk.StateFlags.NORMAL))
        if area.get_size_request() != (width, height):
            area.set_size_request(width, height)

    @staticmethod
    def draw_ring(area, cr, mounted):
        width, height = area.get_allocated_width(), area.get_allocated_height()
        radius = min(width, height) * .44
        style = area.get_style_context()
        color = style.get_color(Gtk.StateFlags.NORMAL)
        cr.set_line_width(max(1, radius * .10))
        cr.set_line_cap(1)  # Cairo ROUND
        start, sweep = math.pi * .75, math.pi * 1.5
        cr.set_source_rgba(color.red, color.green, color.blue, .15)
        cr.arc(width / 2, height / 2, radius, start, start + sweep)
        cr.stroke()
        value = mounted.element.props["value"]
        if value:
            cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
            cr.arc(width / 2, height / 2, radius, start, start + sweep * value)
            cr.stroke()
        return False

    @staticmethod
    def draw_image(area, cr):
        width, height = area.get_allocated_width(), area.get_allocated_height()
        pixbuf = area.artwork
        if pixbuf is not None:
            scale = min(width / pixbuf.get_width(), height / pixbuf.get_height())
            cr.save()
            cr.translate((width - pixbuf.get_width() * scale) / 2,
                         (height - pixbuf.get_height() * scale) / 2)
            cr.scale(scale, scale)
            Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
            cr.paint()
            cr.restore()
        else:
            color = area.get_style_context().get_color(Gtk.StateFlags.NORMAL)
            cr.set_source_rgba(color.red, color.green, color.blue, .12)
            cr.rectangle(0, 0, width, height)
            cr.fill()
            label = area.create_pango_layout("♫")
            w, h = label.get_pixel_size()
            cr.move_to((width - w) / 2, (height - h) / 2)
            cr.set_source_rgba(color.red, color.green, color.blue, .65)
            PangoCairo.show_layout(cr, label)
        return False

    @property
    def visible(self):
        return self.root is not None and self.root.visible

    def render(self, element):
        tree = resolve(element)
        validate_tree(tree)
        self.root = self._reconcile(tree, self.root)
        return self.root.widget

    def _reconcile(self, element, mounted=None):
        if mounted is not None:
            old = mounted.element
            if (old.kind, old.key, old.identity) != (element.kind, element.key, element.identity):
                mounted.widget.destroy()
                mounted = None
        previous = mounted.element.props if mounted is not None else {}
        if mounted is None:
            if element.kind in ("column", "row"):
                widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if element.kind == "column" else Gtk.Orientation.HORIZONTAL)
            elif element.kind == "grid":
                widget = Grid()
            elif element.kind == "icon":
                widget = SvgIcon(element.props["name"])
            elif element.kind == "image":
                widget = Gtk.DrawingArea()
                widget.artwork = None
                widget.get_style_context().add_class("widget-image")
                widget.connect("style-updated", self.size_ring)
                widget.connect("draw", self.draw_image)
            elif element.kind == "text":
                widget = Gtk.Label()
            elif element.kind == "search":
                widget = Gtk.SearchEntry()
                widget.updating = False
                widget.connect("button-press-event", self.focus_search)
            elif element.kind == "slider":
                widget = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
                widget.set_draw_value(False)
                widget.set_can_focus(False)
                widget.updating = False
            elif element.kind == "button":
                widget = Gtk.Button()
                widget.set_focus_on_click(False)
                # Keep one child across loading/ready transitions. GtkButton.set_label()
                # reconstructs its child, which can remain unallocated in the fixed canvas.
                label = Gtk.Label()
                label.show()
                widget.add(label)
            elif element.kind == "ring":
                widget = Gtk.Overlay()
                area = Gtk.DrawingArea()
                area.get_style_context().add_class("progress-ring")
                area.connect("style-updated", self.size_ring)
                area.show()
                widget.add(area)
                widget.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
                widget.content.show()
                widget.add_overlay(widget.content)
                widget.set_overlay_pass_through(widget.content, True)
            else:
                widget = Gtk.ProgressBar()
            widget.set_no_show_all(True)
            mounted = Mounted(element, widget)
            if element.kind == "button":
                widget.connect("clicked", lambda *_: self.click(mounted))
            elif element.kind == "search":
                widget.connect("changed", lambda *_: self.search_changed(mounted))
                widget.connect("activate", lambda *_: self.search_submitted(mounted))
            elif element.kind == "slider":
                widget.connect("value-changed", lambda *_: self.slider_changed(mounted))
            elif element.kind == "ring":
                area.connect("draw", lambda area, cr: self.draw_ring(area, cr, mounted))
        widget = mounted.widget
        props = element.props
        if props != previous:
            context = widget.get_style_context()
            old_classes = set(previous.get("class_name", "").split())
            new_classes = set(props["class_name"].split())
            for name in old_classes - new_classes:
                context.remove_class(name)
            for name in new_classes - old_classes:
                context.add_class(name)
            widget.set_halign(getattr(Gtk.Align, props["align"].upper()))
            widget.set_hexpand(props["expand"])
            widget.set_visible(props["visible"])
            if element.kind in ("column", "row"):
                widget.set_spacing(props["spacing"])
                widget.set_homogeneous(props.get("homogeneous", False))
            elif element.kind == "icon":
                widget.set_icon_name(props["name"])
                widget.set_tooltip_text(props["label"] or None)
                widget.get_accessible().set_name(props["label"])
            elif element.kind == "image":
                if props["data"] != previous.get("data"):
                    widget.artwork = None
                    if props["data"]:
                        loader = GdkPixbuf.PixbufLoader()
                        loader.connect("size-prepared", lambda loader, w, h: loader.set_size(
                            max(1, round(w * min(1, 512 / max(w, h)))),
                            max(1, round(h * min(1, 512 / max(w, h))))))
                        try:
                            loader.write(props["data"])
                            loader.close()
                            widget.artwork = loader.get_pixbuf()
                        except GLib.Error:
                            try:
                                loader.close()
                            except GLib.Error:
                                pass
                    widget.queue_draw()
            elif element.kind == "text":
                widget.set_text(props["text"])
                widget.set_line_wrap(props["wrap"])
                widget.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                widget.set_max_width_chars(props["max_width_chars"])
                widget.set_xalign({"start": 0.0, "center": 0.5, "end": 1.0, "fill": 0.5}[props["align"]])
            elif element.kind == "search":
                widget.updating = True
                try:
                    if widget.get_text() != props["text"]:
                        widget.set_text(props["text"])
                    widget.set_placeholder_text(props["placeholder"])
                    widget.get_accessible().set_name(props["placeholder"])
                finally:
                    widget.updating = False
            elif element.kind == "slider":
                widget.updating = True
                try:
                    widget.set_value(props["value"])
                    widget.set_sensitive(props["sensitive"])
                    widget.set_tooltip_text(props["label"])
                    widget.get_accessible().set_name(props["label"])
                finally:
                    widget.updating = False
            elif element.kind == "button":
                child = widget.get_child()
                if props["system_icon"] is not None:
                    if not isinstance(child, Gtk.Box):
                        child.destroy()
                        child = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                        child.image = AppIcon()
                        child.label = Gtk.Label(xalign=0)
                        child.label.set_ellipsize(Pango.EllipsizeMode.END)
                        child.label.set_width_chars(22)
                        child.label.set_max_width_chars(22)
                        child.pack_start(child.image, False, False, 0)
                        child.pack_start(child.label, True, True, 0)
                        widget.add(child)
                        child.show_all()
                    vertical = props["icon_position"] == "top"
                    child.set_orientation(Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL)
                    child.set_spacing(8 if vertical else 12)
                    child.label.set_xalign(.5 if vertical else 0)
                    child.label.set_width_chars(12 if vertical else 22)
                    child.label.set_max_width_chars(12 if vertical else 22)
                    child.image.set_app_icon(props["system_icon"], 48 if vertical else 32)
                    child.label.set_text(props["text"])
                    child.label.set_no_show_all(not props["show_label"])
                    child.label.set_visible(props["show_label"])
                elif props["icon"] is not None:
                    if not isinstance(child, SvgIcon):
                        child.destroy()
                        child = SvgIcon(props["icon"])
                        widget.add(child)
                        child.show()
                    else:
                        child.set_icon_name(props["icon"])
                else:
                    if not isinstance(child, Gtk.Label):
                        child.destroy()
                        child = Gtk.Label()
                        widget.add(child)
                        child.show()
                    child.set_text(props["text"])
                if (props["text"], props["icon"], props["system_icon"]) != (previous.get("text"), previous.get("icon"), previous.get("system_icon")):
                    widget.queue_resize()
                    if widget.get_realized():
                        widget.size_allocate(widget.get_allocation())
                widget.set_sensitive(props["sensitive"])
                widget.set_tooltip_text(props["tooltip"] or None)
                widget.get_accessible().set_name(props["tooltip"] or props["text"])
            elif element.kind == "ring":
                widget.queue_draw()
            elif element.kind == "progress":
                widget.set_fraction(props["value"])
                widget.set_show_text(props["text"] is not None)
                widget.set_text(props["text"])
            apply_style(widget, element.kind, props)
        if element.kind in ("column", "row", "ring", "grid"):
            container = widget.content if element.kind == "ring" else widget
            old_children = mounted.children
            keyed = {child.element.key: child for child in old_children if child.element.key is not None}
            children, used = [], set()
            for index, child in enumerate(element.children):
                old = keyed.get(child.key) if child.key is not None else (
                    old_children[index] if index < len(old_children) and old_children[index].element.key is None else None)
                if old is not None:
                    used.add(id(old))
                rendered = self._reconcile(child, old)
                expand = child.props.get("style", {}).get("expand", child.props["expand"])
                if rendered.widget.get_parent() is None:
                    if element.kind == "grid":
                        container.attach(rendered.widget, 0, index, 1, 1)
                    else:
                        container.pack_start(rendered.widget, expand, expand, 0)
                if element.kind != "grid":
                    container.set_child_packing(rendered.widget, expand, expand, 0, Gtk.PackType.START)
                    container.reorder_child(rendered.widget, index)
                children.append(rendered)
            for child in old_children:
                if id(child) not in used:
                    child.widget.destroy()
            mounted.children = children
            if element.kind == "grid":
                style = props.get("style", {})
                columns, rows = style.get("columns", props["columns"]), style.get("rows", props["rows"])
                positions = grid_positions(element.children, len(columns))
                widget.configure(columns, rows, [(child.widget, *cell) for child, cell in zip(children, positions)],
                                 round(style.get("columnGap", style.get("gap", props["spacing"]))),
                                 round(style.get("rowGap", style.get("gap", props["spacing"]))))
            if element.kind == "ring":
                # Overlay child requisitions don't change the ring's outer size. Allocate
                # its box again so a wider hours value gets its new natural width.
                container.queue_resize()
                if container.get_realized():
                    container.size_allocate(container.get_allocation())
        mounted.element = element
        return mounted

    def find(self, key):
        """Return a native widget by its key, for inspection or native GTK integration."""
        def walk(node):
            if node.element.key == key:
                return node.widget
            for child in node.children:
                found = walk(child)
                if found is not None:
                    return found
            return None
        return walk(self.root) if self.root is not None else None

    def controls(self):
        def walk(node):
            if node.element.kind in ("button", "search", "slider") and node.widget.get_mapped():
                yield node.widget
            for child in node.children:
                yield from walk(child)
        return tuple(walk(self.root)) if self.root is not None else ()

    def buttons(self):
        return tuple(widget for widget in self.controls() if isinstance(widget, Gtk.Button))

    def close(self):
        if self.root is not None:
            self.root.widget.destroy()
            self.root = None
