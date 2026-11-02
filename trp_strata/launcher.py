"""Installed desktop applications and favourites, launched through Gio."""
import locale


class DesktopApps:
    def __init__(self, changed):
        from gi.repository import Gio
        self.Gio = Gio
        self.monitor = Gio.AppInfoMonitor.get()
        self.monitor_handler = self.monitor.connect("changed", changed)
        source = Gio.SettingsSchemaSource.get_default()
        schema = source.lookup("org.gnome.shell", True) if source else None
        self.settings = Gio.Settings.new_full(schema, None, None) if schema and schema.has_key("favorite-apps") else None
        self.settings_handler = self.settings.connect("changed::favorite-apps", changed) if self.settings else None

    def applications(self):
        return self.Gio.AppInfo.get_all()

    def favourites(self):
        return self.settings.get_strv("favorite-apps") if self.settings else []

    def launch(self, app):
        # Gio handles desktop-file arguments, terminal apps and D-Bus activation.
        from gi.repository import Gdk, Gtk
        display = Gdk.Display.get_default()
        context = display.get_app_launch_context() if display else self.Gio.AppLaunchContext()
        if display:
            context.set_timestamp(Gtk.get_current_event_time())
        if not app.launch([], context):
            raise RuntimeError("The application could not be started.")

    def close(self):
        self.monitor.disconnect(self.monitor_handler)
        if self.settings_handler is not None:
            self.settings.disconnect(self.settings_handler)


class LauncherModel:
    def __init__(self, backend_factory=DesktopApps):
        self.dirty = True
        self.page = 0
        self.query = ""
        self.status = ""
        self.apps = {}
        self.options = None
        self.backend = backend_factory(self.invalidate)

    def invalidate(self, *_args):
        self.dirty = True

    def view(self, apps=None, page_size=6):
        if apps is not None and (not isinstance(apps, (list, tuple)) or
                                 any(not isinstance(item, str) or not item.endswith(".desktop") for item in apps)):
            raise ValueError("Launcher apps must be a list of .desktop application IDs")
        if type(page_size) is not int or not 1 <= page_size <= 20:
            raise ValueError("Launcher page_size must be between 1 and 20")
        options = (tuple(apps) if apps is not None else None, page_size)
        if options != self.options:
            self.page = 0
            self.options = options
        if self.dirty:
            self.apps = {app.get_id(): app for app in self.backend.applications()
                         if app.get_id() and app.should_show()}
            self.favourites = self.backend.favourites()
            self.dirty = False
        pinned = list(dict.fromkeys(apps if apps is not None else self.favourites))
        pinned = [self.apps[app_id] for app_id in pinned if app_id in self.apps]
        query = self.query.strip().casefold()
        all_apps = bool(query) or (apps is None and not pinned)
        entries = sorted(self.apps.values(), key=lambda app: locale.strxfrm(app.get_display_name().casefold())) if all_apps else pinned
        if query:
            entries = [app for app in entries if all(word in " ".join((
                app.get_display_name(), app.get_description() or "", app.get_id())).casefold()
                for word in query.split())]
        pages = max(1, (len(entries) + page_size - 1) // page_size)
        self.page = min(self.page, pages - 1)
        return entries[self.page * page_size:(self.page + 1) * page_size], pages, all_apps

    def set_query(self, text):
        self.query = text
        self.page = 0
        self.status = ""

    def move(self, delta):
        self.page = max(0, self.page + delta)

    def launch(self, app_id):
        app = self.apps.get(app_id)
        if app is None:
            self.status = "Application no longer available."
            return
        try:
            self.backend.launch(app)
            self.status = f"Opening {app.get_display_name()}…"
        except Exception as error:
            self.status = f"Could not open {app.get_display_name()}: {error}"

    def close(self):
        self.backend.close()
