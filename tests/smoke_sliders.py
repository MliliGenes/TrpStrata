"""Native slider interaction and programmatic refresh without hardware writes."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trp_strata.components import Column, Slider
from trp_strata.gtk_renderer import Renderer
from gi.repository import Gtk


def main():
    if not Gtk.init_check()[0]:
        raise SystemExit("Run with a GTK 3 display")
    changes = []
    renderer = Renderer()
    window = Gtk.OffscreenWindow()
    def tree(value, enabled=True):
        return Column(Slider(value, label="Volume", on_change=changes.append, sensitive=enabled, key="volume"))
    try:
        window.add(renderer.render(tree(30)))
        window.show_all()
        while Gtk.events_pending():
            Gtk.main_iteration()
        slider = renderer.find("volume")
        assert slider in renderer.controls()
        assert changes == []
        slider.set_value(65)
        assert changes == [65]
        renderer.render(tree(80))
        assert renderer.find("volume") is slider
        assert slider.get_value() == 80
        assert changes == [65]
        renderer.interactive = False
        slider.set_value(55)
        assert changes == [65]
        renderer.render(tree(40, False))
        assert not slider.get_sensitive()
        print("Sliders: native input, refresh without feedback, arrange mode and disabled state passed")
    finally:
        renderer.close()
        window.destroy()


if __name__ == "__main__":
    main()
