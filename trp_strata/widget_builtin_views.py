"""Default declarative views. Export as JSON to customize without changing logic."""


def bind(path):
    return {"$bind": path if "." in path or path in ("item", "index") else f"state.{path}"}


def node(kind, *children, **props):
    return {"type": kind, **props, **({"children": list(children)} if children else {})}


def text(value, **props):
    return node("Text", text=value, **props)


def repeat(path, template):
    return {"repeat": bind(path), "key": "id", "template": template}


def event(name, args=None, kind="click"):
    return {kind: name if args is None else {"handler": name, "args": args}}


def button(label, action, args=None, **props):
    return node("Button", text=label, events=event(action, args), **props)


def column(*children, **props):
    return node("Column", *children, **props)


def row(*children, **props):
    return node("Row", *children, **props)


def title(value):
    return text(value, class_name="widget-label", align="start")


def detail(value, **props):
    return text(value, wrap=True, max_width_chars=30, align="start", **props)


VIEWS = {
    "Clock": ("clock", column(
        text(bind("time"), class_name="clock-time", key="time"),
        text(bind("date"), class_name="clock-date", visible=bind("show_date"), key="date"),
        spacing=10, class_name="desktop-clock", visible=bind("visible"))),
    "Notes": ("notes", column(title(bind("title")),
        text(bind("text"), class_name="notes-text", align="start", wrap=True, max_width_chars=25),
        spacing=12, class_name="notes-card")),
    "Calendar": ("calendar", column(title(bind("month")),
        text(bind("day"), class_name="calendar-day", align="start"),
        node("Grid", repeat("cells", text(bind("item.text"), class_name=bind("item.class"), expand=True)),
             columns=["1fr"] * 7, spacing=2), spacing=4, class_name="calendar-card")),
    "System": ("system", column(title("SYSTEM"),
        repeat("metrics", column(
            row(text(bind("item.id"), align="start", expand=True),
                text(bind("item.text"), class_name="metric-value")),
            node("Progress", value=bind("item.value"), visible=bind("item.available")), spacing=5)),
        spacing=12, class_name="system-card")),
    "NowPlaying": ("now-playing", column(
        text("NOW PLAYING", class_name="widget-label", key="label"),
        node("Image", data=bind("artwork"), class_name="media-artwork", key="artwork"),
        text(bind("title"), wrap=True, max_width_chars=28, class_name="media-title", key="title"),
        text(bind("artist"), visible=bind("show_artist"), wrap=True, max_width_chars=28, key="artist"),
        text(bind("album"), visible=bind("show_album"), wrap=True, max_width_chars=28, class_name="media-detail", key="album"),
        row(repeat("controls", button(bind("item.label"), "control", bind("item.id"), icon=bind("item.icon"),
            tooltip=bind("item.label"), sensitive=bind("item.enabled"), expand=True, class_name="media-control")), spacing=8),
        text(bind("status"), wrap=True, max_width_chars=28, class_name="media-detail", key="status"),
        spacing=8, class_name="media-card")),
    "Cleaner": ("cleaner", column(title("HOME CLEANER"),
        text(bind("status"), wrap=True, max_width_chars=36, align="start"),
        text("Close VS Code and Firefox first.", wrap=True, max_width_chars=36),
        row(button("Scan", "scan", sensitive=bind("enabled")), button("Clean caches", "clean", sensitive=bind("enabled")), spacing=8),
        spacing=12, class_name="system-card")),
    "Logtime": ("logtime", column(
        text(bind("login"), class_name="logtime-login", key="login"),
        node("Ring", text(bind("percent"), class_name="logtime-percent", key="percent"),
             text(bind("hours"), class_name="logtime-hours", key="hours"), text("Hours", class_name="logtime-unit"),
             value=bind("fraction"), class_name="logtime-ring", key="ring"),
        text(bind("month"), class_name="widget-label", key="month"),
        text(bind("period"), class_name="logtime-period", key="period"),
        row(button("Prev", "shift", -1, expand=True, key="prev"), button("Next", "shift", 1, expand=True, key="next"), spacing=8),
        button(bind("refresh_label"), "reload", sensitive=bind("can_refresh"), key="refresh"),
        text(bind("status"), wrap=True, max_width_chars=30, class_name="logtime-status", key="status"),
        spacing=8, class_name="logtime-card")),
    "FileSearch": ("file-search", column(
        row(text(bind("title"), class_name="widget-label", align="start", expand=True),
            button("Refresh", "reload", sensitive=bind("can_refresh")), spacing=8),
        node("Search", text=bind("query"), events=event("search", kind="change"), placeholder="Find files by name…", key="file-query"),
        column(repeat("results", column(
            button(bind("item.name"), "launch", bind("item.id"), system_icon=bind("item.icon"), tooltip=bind("item.id")),
            text(bind("item.directory"), align="start", wrap=True, max_width_chars=36, class_name="file-search-path"), spacing=3)), spacing=8),
        text("Type a name, abbreviation or a few words from the path.", visible=bind("show_hint"), wrap=True, max_width_chars=36, align="start"),
        text(bind("status"), wrap=True, max_width_chars=36, align="start", class_name="file-search-path"),
        spacing=10, class_name="launcher-card file-search-card")),
    "Launcher": ("launcher", column(title(bind("title")),
        node("Search", text=bind("query"), events=event("search", kind="change"), placeholder="Search installed apps…", key="app-search"),
        node("Grid", repeat("apps", button(bind("item.name"), "launch", bind("item.id"),
            system_icon=bind("item.icon"), tooltip=bind("item.tooltip"), icon_position="top", expand=True, class_name="launcher-app")),
            repeat("empty", column(class_name="launcher-empty", expand=True)), columns=["1fr"] * 3, spacing=8),
        detail(bind("hint"), visible=bind("show_hint")),
        row(button("Previous", "move", -1, sensitive=bind("can_previous")), text(bind("page"), expand=True),
            button("Next", "move", 1, sensitive=bind("can_next")), visible=bind("show_pages"), spacing=8),
        detail(bind("status"), visible=bind("show_status")), spacing=10, class_name="launcher-card")),
    "QuickLinks": ("quick-links", column(title(bind("title")),
        repeat("links", button(bind("item.label"), "launch", bind("item"), system_icon=bind("item.icon"), tooltip=bind("item.url"))),
        detail("Add websites using Edit beside Quick links in the app.", visible=bind("show_hint")),
        detail(bind("status"), visible=bind("show_status")), spacing=10, class_name="launcher-card quick-links-card")),
}

DEVICE_VIEW = column(
    row(text(bind("title"), class_name="widget-label", align="start", expand=True), text(bind("level")), spacing=8),
    node("Slider", value=bind("value"), label=bind("label"), events=event("change", kind="change"), sensitive=bind("available"), key="level"),
    button(bind("mute_label"), "mute", sensitive=bind("available"), visible=bind("show_mute")),
    text(bind("error"), visible=bind("show_error"), wrap=True, max_width_chars=32, align="start"),
    spacing=10, class_name="launcher-card device-card")
VIEWS["Volume"] = ("volume", DEVICE_VIEW)
VIEWS["Brightness"] = ("brightness", DEVICE_VIEW)


def document(name):
    controller, view = VIEWS[name]
    return {"version": 1, "controller": controller, "view": view}
