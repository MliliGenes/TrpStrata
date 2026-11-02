"""Resolve application icons through the desktop's themes and exported app paths."""
import os

from gi.repository import Gio, GLib, Gtk


def icon_paths():
    home = os.path.expanduser("~")
    roots = [GLib.get_user_data_dir(), *GLib.get_system_data_dirs(),
             os.path.join(home, ".local/share"), "/usr/local/share", "/usr/share",
             os.path.join(home, ".local/share/flatpak/exports/share"),
             "/var/lib/flatpak/exports/share", "/var/lib/snapd/desktop"]
    paths = [os.path.join(home, ".icons")]
    for root in roots:
        paths.extend(os.path.join(root, kind) for kind in ("icons", "pixmaps"))
    return tuple(dict.fromkeys(paths))


class AppIcon(Gtk.Image):
    """Load actual pixels, retaining theme-change refresh and file-icon support."""
    def __init__(self):
        super().__init__()
        self.serialized = None
        self.size = 32
        self.theme = Gtk.IconTheme.get_default()
        paths = self.theme.get_search_path()
        extra = [path for path in icon_paths() if path not in paths and os.path.isdir(path)]
        if extra:
            self.theme.set_search_path([*paths, *extra])
        self.handler = self.theme.connect("changed", lambda *_: self.refresh())
        self.connect("notify::scale-factor", lambda *_: self.refresh())
        self.connect("destroy", lambda *_: self.theme.disconnect(self.handler))

    def set_app_icon(self, serialized, size):
        if (serialized, size) != (self.serialized, self.size):
            self.serialized, self.size = serialized, size
            self.refresh()

    def refresh(self):
        if self.serialized is None:
            return
        candidates = []
        try:
            candidates.append(Gio.Icon.new_for_string(self.serialized))
        except GLib.Error:
            pass
        candidates.extend(Gio.ThemedIcon.new(name) for name in
                          ("application-x-executable", "application-x-executable-symbolic", "image-missing"))
        scale = self.get_scale_factor()
        for icon in candidates:
            info = self.theme.lookup_by_gicon_for_scale(icon, self.size, scale, Gtk.IconLookupFlags.FORCE_SIZE)
            if info is None:
                continue
            try:
                pixbuf = info.load_icon()
            except GLib.Error:
                continue
            if pixbuf is not None:
                # A Cairo surface retains the correct logical size on HiDPI displays.
                from gi.repository import Gdk
                self.set_from_surface(Gdk.cairo_surface_create_from_pixbuf(pixbuf, scale, None))
                return
        self.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
