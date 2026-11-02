"""Native GTK 3 launcher sizing and icon checks, without launching applications."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trp_strata.components import Button, Column, Row, Search
from trp_strata.gtk_renderer import Renderer
from gi.repository import Gio, Gtk


def main():
    if not Gtk.init_check()[0]:
        raise SystemExit("Run this check with a GTK 3 display")
    renderer = Renderer()
    window = Gtk.OffscreenWindow()
    clicks = []
    queries = []

    def tree(icon):
        return Column(
            Search(queries[-1] if queries else "", on_change=queries.append, key="search"),
            Row(Button("Files", system_icon=icon, icon_position="top", key="short", on_click=lambda: clicks.append("files")),
            Button("An application with an unusually long name that should never widen the card",
                   system_icon="missing-test-application-icon", icon_position="top", key="long", on_click=lambda: None),
            Button("Terminal", system_icon="utilities-terminal", icon_position="top", key="third", on_click=lambda: None),
            homogeneous=True, spacing=8),
        )

    try:
        window.add(renderer.render(tree("system-file-manager")))
        window.show_all()
        while Gtk.events_pending():
            Gtk.main_iteration()
        short, long = renderer.find("short"), renderer.find("long")
        assert short.get_preferred_width() == long.get_preferred_width()
        assert short.get_preferred_height() == long.get_preferred_height()
        assert short.get_allocated_width() == long.get_allocated_width()
        search = renderer.find("search")
        assert search in renderer.controls()
        search.set_text("terminal")
        assert queries == ["terminal"]
        child = short.get_child()
        assert child.image.size == 48
        assert child.image.get_storage_type() == Gtk.ImageType.SURFACE
        assert child.image.serialized == "system-file-manager"
        assert long.get_child().image.get_storage_type() == Gtk.ImageType.SURFACE
        third = renderer.find("third")
        assert abs(short.get_allocated_width() - third.get_allocated_width()) <= 1
        assert short.get_allocation().x < long.get_allocation().x < third.get_allocation().x
        short.clicked()
        assert clicks == ["files"]
        renderer.render(tree("web-browser"))
        assert renderer.find("search") is search
        assert search.get_text() == "terminal"
        assert queries == ["terminal"]  # Renders must not emit another user edit.
        assert renderer.find("short").get_child() is child
        assert child.image.serialized == "web-browser"
        assert child.image.get_storage_type() == Gtk.ImageType.SURFACE
        # File-backed icons (common for third-party apps) also use the Gio path.
        renderer.render(tree(Gio.FileIcon.new(Gio.File.new_for_path(
            str(Path(__file__).resolve().parents[1] / "trp_strata/assets/fontawesome/solid/music.svg"))).to_string()))
        assert child.image.get_storage_type() == Gtk.ImageType.SURFACE
        print("Launcher icons, equal dimensions, live search, updates and click callbacks: passed")
    finally:
        renderer.close()
        window.destroy()


if __name__ == "__main__":
    main()
