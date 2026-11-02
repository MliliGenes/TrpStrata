"""Compatibility API for exporting built-in package views as standalone JSON."""
import json

from .widget_packages import DIRECTORY, PACKAGES

VIEWS = PACKAGES


def document(name):
    folder, controller = PACKAGES[name]
    source = json.loads((DIRECTORY / folder / "view.json").read_text())
    return {**source, "controller": controller}
