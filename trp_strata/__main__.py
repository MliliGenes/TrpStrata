"""Module entry point; command parsing lives in cli.py."""
from .native_wallpaper import prepare_environment

prepare_environment()

from .cli import main

raise SystemExit(main())
