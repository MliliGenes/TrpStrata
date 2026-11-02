"""Terminal interface; inspection and configuration storage work without GTK."""
import argparse
import json
import os
import sys

from . import settings, storage


def parser():
    result = argparse.ArgumentParser(prog="trpstrata", description="Wallpaper, desktop colours and CSS-styled widgets.")
    commands = result.add_subparsers(dest="command")
    for name, help_text in {
        "open": "Open the window", "desktop": "Run the login helper",
        "next": "Choose another wallpaper", "light": "Use light colours",
        "dark": "Use dark colours", "auto": "Follow the configured hours",
        "apply": "Reapply the current colours", "restore": "Restore the original desktop",
        "status": "Print configuration, wallpaper state and awake request as JSON",
        "shell-init": "Print optional Bash/Zsh aliases",
        "tui": "Open the interactive terminal control panel",
        "lock": "Show trpStrata's themed lock overlay",
        "paths": "Show installation, cache and configuration locations",
    }.items():
        commands.add_parser(name, help=help_text)
    commands.add_parser("set", help="Use an image or video").add_argument("file")
    commands.add_parser("awake", help="Keep awake: minutes, on, or off").add_argument("duration", nargs="?", default="60")
    commands.add_parser("clock", help="Show or hide the desktop clock").add_argument("action", choices=("on", "off", "toggle"), nargs="?", default="toggle")
    layout_parser = commands.add_parser("layout", help="Arrange desktop widgets, toggle individual cards or reset their layout")
    layout_parser.add_argument("action", choices=("edit", "done", "reset", "path", "list", "enable", "disable", "toggle"), nargs="?", default="edit")
    layout_parser.add_argument("widget_id", nargs="?")
    widget = commands.add_parser("widget", help="Manage widget packages and desktop instances")
    widget.add_argument("action", choices=("export", "list", "copy", "add", "remove"))
    widget.add_argument("name", nargs="?")
    widget.add_argument("destination", nargs="?")
    config = commands.add_parser("config", help="Inspect or change preferences").add_subparsers(dest="config_command")
    config.add_parser("list", help="List values and descriptions")
    config.add_parser("path", help="Print the configuration file path")
    config.add_parser("get", help="Read one value").add_argument("key", choices=sorted(settings.DEFAULT_CONFIG))
    change = config.add_parser("set", help="Validate, save, and apply one preference")
    change.add_argument("key", choices=sorted(settings.DEFAULT_CONFIG))
    change.add_argument("value")
    config.add_parser("reset", help="Reset one preference or all preferences").add_argument("key", nargs="?", choices=sorted(settings.DEFAULT_CONFIG))
    return result


def apply_config():
    # Headless edits take effect at the next helper startup. Live helpers watch config.json.
    if os.environ.get("DISPLAY"):
        from . import core
        core.apply_theme()
        core.start_helper()


def main(argv=None):
    # Ghostty's AppImage can export a private settings backend which GNOME never reads.
    if os.environ.get("GSETTINGS_BACKEND") == "keyfile":
        os.environ["GSETTINGS_BACKEND"] = "dconf"
    args = parser().parse_args(argv)
    command = args.command or "open"
    try:
        if command == "widget":
            from .widget_builtin_views import VIEWS, document
            if args.action == "list":
                print("\n".join(VIEWS))
            elif args.action == "copy":
                from .widget_packages import copy_builtin
                if args.name is None or args.destination is None:
                    raise ValueError("usage: trpstrata widget copy BUILTIN NAME")
                path = copy_builtin(args.name, args.destination)
                print(f"Created {path}")
                print("Edit view.json for presentation and controller.py for logic.")
                print(f"Place it on the desktop with: trpstrata widget add {args.destination}")
            elif args.action == "add":
                from .layout import add_widget
                if args.name is None:
                    raise ValueError("usage: trpstrata widget add COMPONENT [ID]")
                widget_id = add_widget(args.name, args.destination)
                apply_config()
                print(f"Added {widget_id} ({args.name}). Use 'trpstrata layout edit' to position it.")
            elif args.action == "remove":
                from .layout import remove_widget
                if args.name is None or args.destination is not None:
                    raise ValueError("usage: trpstrata widget remove ID")
                remove_widget(args.name)
                apply_config()
                print(f"Removed {args.name} from the layout; its widget package is preserved.")
            else:
                if args.name not in VIEWS:
                    raise ValueError("Choose a built-in widget from: " + ", ".join(VIEWS))
                print(json.dumps(document(args.name), indent=2, ensure_ascii=False))
            return 0
        if command == "tui":
            from . import tui
            return tui.main()
        if command == "lock":
            from . import lockscreen
            if not settings.load_config().get("lock_password"):
                raise ValueError("set config lock_password before locking")
            lockscreen.run()
            return 0
        if command == "paths":
            print(json.dumps({"app": storage.PATHS.app, "cache": storage.CACHE_DIR,
                              "config": storage.CONFIG_DIR, "themes": storage.PATHS.themes,
                              "bulk_storage": storage.PATHS.bulk}, indent=2))
            return 0
        if command == "layout":
            from . import layout
            if args.action == "path":
                print(storage.LAYOUT)
            elif args.action == "list":
                layout.ensure_layout()
                config = settings.load_config()
                for placement in layout.load_layout():
                    print(f"{placement.id:20} {'on' if layout.widget_enabled(placement, config) else 'off':4} {layout.widget_title(placement)}")
            elif args.action in ("enable", "disable", "toggle"):
                if not args.widget_id:
                    raise ValueError(f"usage: trpstrata layout {args.action} WIDGET_ID")
                layout.ensure_layout()
                placement = next((item for item in layout.load_layout() if item.id == args.widget_id), None)
                if placement is None:
                    raise ValueError(f"Unknown widget: {args.widget_id}")
                enabled = not layout.widget_enabled(placement, settings.load_config()) if args.action == "toggle" else args.action == "enable"
                layout.set_enabled(args.widget_id, enabled)
                apply_config()
                print(f"{args.widget_id}: {'on' if enabled else 'off'}")
            else:
                layout.ensure_layout()
                if args.action == "reset":
                    storage.write(storage.LAYOUT, layout.DEFAULT_FILE.read_text())
                    settings.save_config(widgets_enabled=True)
                elif args.action == "edit":
                    settings.save_config(layout_edit=True, widgets_enabled=True)
                else:
                    settings.save_config(layout_edit=False)
                apply_config()
                print("Layout reset." if args.action == "reset" else
                      "Arrange mode on: drag inside to move, drag any edge/corner to resize, scroll to scale text." if args.action == "edit" else
                      "Arrange mode off; desktop widgets are click-through.")
            return 0
        if command == "config":
            action = args.config_command or "list"
            if action == "path":
                print(storage.CONFIG)
            elif action == "get":
                value = settings.load_config()[args.key]
                print(value if isinstance(value, str) else json.dumps(value))
            elif action in ("set", "reset"):
                if action == "set":
                    config = settings.save_config(**{args.key: args.value})
                else:
                    config = settings.reset_config(args.key)
                apply_config()
                print(json.dumps(config[args.key] if args.key else config, indent=2))
            else:
                for key, value in settings.load_config().items():
                    print(f"{key:20} {json.dumps(value):32} {settings.DESCRIPTIONS[key]}")
            return 0
        if command == "status":
            print(json.dumps({"config": settings.load_config(), "state": storage.read_json(storage.STATE, {}),
                              "awake": storage.read_json(storage.AWAKE, {})}, indent=2))
            return 0
        if command == "shell-init":
            print("alias wnext='trpstrata next'\n"
                  "alias wawake='trpstrata awake'\nalias wclock='trpstrata clock'")
            return 0
        if command == "clock":
            from . import layout
            enabled = not settings.load_config()["clock"] if args.action == "toggle" else args.action == "on"
            layout.ensure_layout()
            for placement in layout.load_layout():
                if placement.component == "Clock":
                    layout.save_placement(placement.id, enabled=enabled)
            settings.save_config(clock=enabled)
            apply_config()
            print(f"Desktop clock {'on' if enabled else 'off'}.")
            return 0
        if command in ("light", "dark", "auto"):
            settings.save_config(mode=command)
            apply_config()
            return 0
        if command == "open":
            from . import app
            return app.main()
        if command == "desktop":
            from . import desktop
            return desktop.main()

        from . import core
        if command == "set":
            core.set_wallpaper(args.file)
            core.start_helper()
        elif command == "next":
            if core.next_wallpaper() is None:
                print("trpstrata: no other pictures in", core.load_config()["folder"], file=sys.stderr)
                return 1
            core.start_helper()
        elif command == "apply":
            core.apply_theme()
        elif command == "awake":
            arg = args.duration
            if arg == "off":
                core.keep_awake(None)
                print("Screen locks normally again.")
            elif arg == "on" or (arg.isdigit() and int(arg) > 0):
                core.keep_awake(core.FOREVER if arg == "on" else int(arg))
                print("Keep awake on until logout or 'awake off'." if arg == "on" else f"Keep awake on for {arg} minutes.")
            else:
                raise ValueError("usage: trpstrata awake [MINUTES|on|off]")
        elif command == "restore":
            core.restore()
        return 0
    except (ValueError, OSError, ImportError) as e:
        print(f"trpstrata: {e}", file=sys.stderr)
        return 1
