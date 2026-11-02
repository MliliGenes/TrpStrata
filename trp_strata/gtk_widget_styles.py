"""Apply structured styles after component defaults; removal restores those defaults."""
from functools import lru_cache
from gi.repository import Gtk, Pango

from .widget_styles import css


@lru_cache(maxsize=256)
def provider_for(source):
    provider = Gtk.CssProvider()
    provider.load_from_data(source.encode())
    return provider


def validate_tree(tree):
    provider_for(css(tree.props.get("style", {})))
    for child in tree.children:
        validate_tree(child)


def apply(widget, kind, props):
    style = props.get("style", {})
    previous = getattr(widget, "structured_style", None)
    if style != previous:
        provider = provider_for(css(style))
        context = widget.get_style_context()
        old = getattr(widget, "structured_provider", None)
        if old is not None:
            context.remove_provider(old)
        context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 10)
        widget.structured_provider = provider
        widget.structured_style = dict(style)
    if kind in ("image", "icon"):
        context = widget.get_style_context()
        default = 16 if kind == "icon" else 1
        width = context.get_property("min-width", widget.get_state_flags()) or default
        height = context.get_property("min-height", widget.get_state_flags()) or default
    else:
        width = height = -1
    widget.set_size_request(round(style.get("width", width)), round(style.get("height", height)))
    widget.set_halign(getattr(Gtk.Align, style.get("alignSelf", props["align"]).upper()))
    widget.set_valign(getattr(Gtk.Align, style.get("valignSelf", "fill").upper()))
    widget.set_hexpand(style.get("expand", props["expand"]))
    widget.set_vexpand(style.get("vexpand", False))
    if kind in ("row", "column"):
        widget.set_spacing(round(style.get("gap", props["spacing"])))
    if kind == "text":
        widget.set_xalign({"start": 0, "center": .5, "end": 1, "fill": .5}[
            style.get("textAlign", props["align"])])
        widget.set_line_wrap(style.get("wrap", props["wrap"]))
        widget.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
