"""Built-in widget packages: a JSON view and a Python controller per widget."""
from importlib import import_module
from pathlib import Path

DIRECTORY = Path(__file__).parent
# Public component name -> package folder, stable controller alias for flat JSON views.
PACKAGES = {
    "Clock": ("clock", "clock"), "Notes": ("notes", "notes"),
    "Calendar": ("calendar", "calendar"), "System": ("system", "system"),
    "NowPlaying": ("now_playing", "now-playing"), "Cleaner": ("cleaner", "cleaner"),
    "Logtime": ("logtime", "logtime"), "FileSearch": ("file_search", "file-search"),
    "Launcher": ("launcher", "launcher"), "QuickLinks": ("quick_links", "quick-links"),
    "Volume": ("volume", "volume"), "Brightness": ("brightness", "brightness"),
}


def controllers():
    from trp_strata.widget_engine import Controller
    return {"static": Controller, **{
        alias: import_module(f"{__name__}.{folder}.controller").Controller
        for folder, alias in PACKAGES.values()}}


def copy_builtin(name, destination):
    """Create an editable user package without replacing existing customizations."""
    from trp_strata import storage
    from trp_strata.layout import MODULE_NAME
    if name not in PACKAGES:
        raise ValueError("Choose a built-in widget from: " + ", ".join(PACKAGES))
    if not isinstance(destination, str) or not MODULE_NAME.fullmatch(destination):
        raise ValueError("Destination must be a widget name, for example my_clock")
    root = Path(storage.CUSTOM_WIDGETS)
    target = root / destination
    if target.exists() or any((root / f"{destination}{suffix}").exists() for suffix in (".json", ".py")):
        raise ValueError(f"Widget {destination!r} already exists; choose another name")
    source = DIRECTORY / PACKAGES[name][0]
    files = {filename: (source / filename).read_text() for filename in ("view.json", "controller.py")}
    root.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    written = []
    try:
        for filename, content in files.items():
            path = target / filename
            with path.open("x") as output:
                written.append(path)
                output.write(content)
    except Exception:
        for path in written:
            path.unlink()
        try:
            target.rmdir()
        except OSError:
            pass
        raise
    return target
