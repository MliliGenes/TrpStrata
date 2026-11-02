"""Built-in widget logic. Views consume plain state and named events."""
import calendar
from datetime import date
import os
import time

from .widget_engine import Controller, handler


class PollingController(Controller):
    interval = 1000

    def mount(self, ctx):
        self.refresh(ctx)
        ctx.every(self.interval, lambda: self.refresh(ctx))

    def props_changed(self, ctx, previous):
        self.refresh(ctx)


class ClockController(PollingController):
    def refresh(self, ctx):
        config, now = ctx.props["config"], time.localtime()
        ctx.set_state(time=time.strftime(config["clock_format"], now),
                      date=time.strftime(config["clock_date_format"], now),
                      show_date=bool(config["clock_date_format"]), visible=config["clock"])


class NotesController(Controller):
    def mount(self, ctx):
        self.props_changed(ctx, {})

    def props_changed(self, ctx, previous):
        from .widgets.notes import DEFAULT_TITLE, DEFAULT_TEXT
        ctx.set_state(title=ctx.props.get("title", DEFAULT_TITLE).upper(), text=ctx.props.get("text", DEFAULT_TEXT))


class CalendarController(PollingController):
    interval = 30000

    def refresh(self, ctx):
        today = date.today()
        cells = [{"id": i, "text": name, "class": "calendar-weekday"}
                 for i, name in enumerate(("M", "T", "W", "Th", "F", "S", "Su"))]
        for index, day in enumerate(day for week in calendar.monthcalendar(today.year, today.month) for day in week):
            cells.append({"id": index + 7, "text": str(day) if day else "",
                          "class": "calendar-cell today" if day == today.day else "calendar-cell"})
        ctx.set_state(month=today.strftime("%B %Y").upper(), day=str(today.day), cells=cells)


class SystemController(PollingController):
    def refresh(self, ctx):
        from .widgets.system import SystemStats
        values = ctx.model("system", SystemStats).sample()
        ctx.set_state(metrics=[{"id": name, "value": value or 0, "available": value is not None,
                                "text": f"{value:.0%}" if value is not None else "Measuring…"}
                               for name, value in values.items()])


class NowPlayingController(PollingController):
    def refresh(self, ctx):
        from .now_playing import NowPlayingModel, PREFIX, can_control
        from .artwork import ArtworkModel
        model = ctx.model("now-playing", NowPlayingModel)
        player, error, busy = model.view()
        props = player["properties"] if player else {}
        metadata = props.get("Metadata", {})
        artwork = ctx.model("artwork", ArtworkModel).view(metadata.get("mpris:artUrl", ""))
        artists = metadata.get("xesam:artist", [])
        artist = artists if isinstance(artists, str) else ", ".join(artists)
        album = metadata.get("xesam:album", "")
        status = props.get("PlaybackStatus", "")
        source = player["name"][len(PREFIX):].split(".")[0] if player else "Open a media player to get started"
        ctx.set_state(title=metadata.get("xesam:title") or ("Unknown track" if player else "Nothing playing"),
                      artist=artist, album=album, show_artist=bool(artist), show_album=bool(album), artwork=artwork,
                      status=error or (f"{source} · {status}" if status else source),
                      controls=[{"id": method, "icon": icon, "label": label,
                                 "enabled": not busy and can_control(player, method)}
                                for method, icon, label in (("Previous", "backward-step", "Previous"),
                                    ("PlayPause", "pause" if status == "Playing" else "play",
                                     "Pause" if status == "Playing" else "Play"), ("Next", "forward-step", "Next"))])

    @handler
    def control(self, ctx, event):
        if event.get("args") not in ("Previous", "PlayPause", "Next"):
            raise ValueError("Unknown playback action")
        ctx.instance.models["now-playing"].control(event["args"])
        self.refresh(ctx)


class CleanerController(PollingController):
    def refresh(self, ctx):
        from .cleaner import CleanerModel
        status, busy = ctx.model("cleaner", CleanerModel).view()
        ctx.set_state(status=status, enabled=not busy)

    @handler
    def scan(self, ctx, event):
        ctx.instance.models["cleaner"].start()
        self.refresh(ctx)

    @handler
    def clean(self, ctx, event):
        ctx.instance.models["cleaner"].start(True)
        self.refresh(ctx)


class LogtimeController(PollingController):
    def refresh(self, ctx):
        from .logtime import LogtimeModel
        from .settings import validate
        config = ctx.props["config"]
        username = validate("logtime_username", ctx.props.get("username") if ctx.props.get("username") is not None else config["logtime_username"])
        goal = validate("logtime_goal", ctx.props.get("goal") if ctx.props.get("goal") is not None else config["logtime_goal"])
        data = ctx.model("logtime", LogtimeModel).view(username)
        hours = data["hours"]
        fraction = min(1, hours / goal) if hours is not None else 0
        status = ("Set logtime_username in settings" if not username else data["error"] or
                  ("Updating…" if data["loading"] and hours is not None else "Loading…" if data["loading"] else f"Goal · {goal:g} hours"))
        ctx.set_state(login=username.upper() if username else "LOGTIME", fraction=fraction,
                      percent=f"{fraction:.0%}" if hours is not None else "—", hours=f"{hours:g}" if hours is not None else "—",
                      month=data["start"].strftime("%B %Y"), period=f'{data["start"]:%b %d, %Y} – {data["end"]:%b %d, %Y}',
                      refresh_label="Updating…" if data["loading"] else "Refresh",
                      can_refresh=bool(username) and not data["loading"], status=status)

    @handler
    def shift(self, ctx, event):
        if event.get("args") not in (-1, 1):
            raise ValueError("Month direction must be -1 or 1")
        ctx.instance.models["logtime"].shift(event["args"])
        self.refresh(ctx)

    @handler
    def reload(self, ctx, event):
        ctx.instance.models["logtime"].refresh()
        self.refresh(ctx)


class DeviceController(PollingController):
    volume = False

    def refresh(self, ctx):
        from .device_controls import DeviceModel, VolumeBackend, BrightnessBackend
        key = "volume" if self.volume else "brightness"
        value, muted, available, error = ctx.model(key, lambda: DeviceModel(VolumeBackend if self.volume else BrightnessBackend)).view()
        title = ctx.props.get("title", "Volume" if self.volume else "Brightness")
        ctx.set_state(title=title.upper(), label=title, value=value, available=available,
                      level="Muted" if self.volume and muted else f"{value}%" if available else "—",
                      mute_label="Unmute" if muted else "Mute", show_mute=self.volume, error=error, show_error=bool(error))

    @handler
    def change(self, ctx, event):
        ctx.instance.models["volume" if self.volume else "brightness"].set_value(event["value"])
        self.refresh(ctx)

    @handler
    def mute(self, ctx, event):
        if self.volume:
            ctx.instance.models["volume"].toggle_mute()
            self.refresh(ctx)


class VolumeController(DeviceController):
    volume = True


class FileSearchController(PollingController):
    def refresh(self, ctx):
        from .file_search import FileSearchModel, file_icon
        root = ctx.props.get("root", "~")
        if not isinstance(root, str) or not root.strip():
            raise ValueError("File Search root must be a folder path")
        model = ctx.model("file-search", lambda: FileSearchModel(root))
        model.configure(root)
        results, status, busy = model.view()
        ctx.set_state(title=ctx.props.get("title", "File search").upper(), query=model.query,
                      can_refresh=not busy, show_hint=not model.query.strip(), status=status,
                      results=[{"id": path, "name": os.path.basename(path), "icon": file_icon(path),
                                "directory": os.path.relpath(os.path.dirname(path), model.root)} for path in results])

    @handler
    def search(self, ctx, event):
        ctx.instance.models["file-search"].set_query(event["value"])
        self.refresh(ctx)

    @handler
    def reload(self, ctx, event):
        ctx.instance.models["file-search"].refresh()
        self.refresh(ctx)

    @handler
    def launch(self, ctx, event):
        ctx.instance.models["file-search"].launch(event["args"])
        self.refresh(ctx)


class LauncherController(PollingController):
    def refresh(self, ctx):
        from .launcher import LauncherModel
        from .widgets.launcher import app_icon
        model = ctx.model("launcher", LauncherModel)
        page_size = ctx.props.get("page_size", 6)
        entries, pages, _ = model.view(ctx.props.get("apps"), page_size)
        apps = [{"id": app.get_id(), "name": app.get_display_name(), "icon": app_icon(app),
                 "tooltip": app.get_display_name() + ("\n" + app.get_description() if app.get_description() else "")}
                for app in entries]
        ctx.set_state(title=ctx.props.get("title", "App launcher").upper(), query=model.query, apps=apps,
                      empty=[{"id": f"empty-{i}"} for i in range(len(apps), ((page_size + 2) // 3) * 3)],
                      hint="No matching applications." if model.query.strip() else "Search to find installed applications.",
                      show_hint=not entries, can_previous=model.page > 0, can_next=model.page + 1 < pages,
                      page=f"{model.page + 1} / {pages}", show_pages=pages > 1, status=model.status, show_status=bool(model.status))

    @handler
    def search(self, ctx, event):
        ctx.instance.models["launcher"].set_query(event["value"])
        self.refresh(ctx)

    @handler
    def move(self, ctx, event):
        if event.get("args") not in (-1, 1):
            raise ValueError("Page direction must be -1 or 1")
        ctx.instance.models["launcher"].move(event["args"])
        self.refresh(ctx)

    @handler
    def launch(self, ctx, event):
        ctx.instance.models["launcher"].launch(event["args"])
        self.refresh(ctx)


class QuickLinksController(PollingController):
    def refresh(self, ctx):
        from .quick_links import DEFAULT_LINKS, QuickLinksModel, normalize_links
        model = ctx.model("quick-links", QuickLinksModel)
        links = normalize_links(ctx.props.get("links", DEFAULT_LINKS))
        ctx.set_state(title=ctx.props.get("title", "Quick links").upper(),
                      links=[{**link, "id": f"link-{index}", "icon": model.icon(link["url"])} for index, link in enumerate(links)],
                      show_hint=not links, status=model.status, show_status=bool(model.status))

    @handler
    def launch(self, ctx, event):
        link = event["args"]
        ctx.instance.models["quick-links"].launch(link["label"], link["url"])
        self.refresh(ctx)


CONTROLLERS = {
    "static": Controller, "clock": ClockController, "calendar": CalendarController, "notes": NotesController,
    "system": SystemController, "now-playing": NowPlayingController, "cleaner": CleanerController,
    "logtime": LogtimeController, "volume": VolumeController, "brightness": DeviceController,
    "file-search": FileSearchController, "launcher": LauncherController, "quick-links": QuickLinksController,
}
