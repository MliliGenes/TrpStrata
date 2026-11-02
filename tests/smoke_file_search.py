"""Native GTK check: typing a fuzzy query renders a clickable file result."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trp_strata.components import component_scope, close_models
from trp_strata.gtk_renderer import Renderer
from trp_strata.widgets.file_search import FileSearch
from gi.repository import Gtk


def main():
    if not Gtk.init_check()[0]:
        raise SystemExit("Run this check with a GTK 3 display")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "report.txt"
        path.write_text("Example")
        models = {}
        window = Gtk.OffscreenWindow()
        def render():
            with component_scope(models):
                return renderer.render(FileSearch(config={}, root=directory))
        renderer = Renderer(on_action=render)
        try:
            window.add(render())
            window.show_all()
            while Gtk.events_pending():
                Gtk.main_iteration()
            model = models["file-search"]
            model.opener = Mock()
            entry = renderer.find("file-query")
            assert entry in renderer.controls()
            entry.set_text("rpt")
            with model.condition:
                assert model.condition.wait_for(lambda: not model.busy, timeout=3)
            render()
            while Gtk.events_pending():
                Gtk.main_iteration()
            result = renderer.find(str(path))
            assert result is not None
            button = result.get_children()[0]
            assert button.get_child().image.get_storage_type() == Gtk.ImageType.SURFACE
            button.clicked()
            model.opener.assert_called_once_with(str(path))
            entry.set_text("")
            with model.condition:
                assert model.condition.wait_for(lambda: not model.busy, timeout=3)
            render()
            assert renderer.find(str(path)) is None
            assert renderer.find("file-query") is entry
            print("File search typing, fuzzy result, icon, open callback and clearing: passed")
        finally:
            close_models(models)
            renderer.close()
            window.destroy()


if __name__ == "__main__":
    main()
