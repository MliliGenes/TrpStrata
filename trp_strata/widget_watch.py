"""Watch custom widget files and one-level widget packages, including atomic saves."""
import logging
from pathlib import Path

from gi.repository import Gio, GLib

log = logging.getLogger(__name__)


class WidgetWatch:
    def __init__(self, directory, on_change):
        self.directory = Path(directory)
        self.on_change = on_change
        self.monitors = {}
        self.closed = False
        self._sync()

    def _sync(self):
        from .layout import MODULE_NAME
        wanted = {self.directory}
        try:
            wanted.update(path for path in self.directory.iterdir()
                          if path.is_dir() and MODULE_NAME.fullmatch(path.name))
        except OSError:
            log.exception("Cannot inspect widget directory %s", self.directory)
        changed = wanted != set(self.monitors)
        for path in set(self.monitors) - wanted:
            self.monitors.pop(path).cancel()
        for path in wanted - set(self.monitors):
            try:
                monitor = Gio.File.new_for_path(str(path)).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
                monitor.connect("changed", self._changed)
                self.monitors[path] = monitor
            except GLib.Error:
                log.exception("Cannot monitor widget directory %s", path)
        return changed

    def _changed(self, monitor, file, other, event):
        if self.closed:
            return
        paths = [Path(item.get_path()) for item in (file, other) if item is not None and item.get_path()]
        changed = self._sync() if any(path.parent == self.directory for path in paths) else False
        if changed or any(path.suffix in (".py", ".json") for path in paths):
            self.on_change()

    def cancel(self):
        self.closed = True
        for monitor in self.monitors.values():
            monitor.cancel()
        self.monitors.clear()
