import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr

from trp_strata import layout, storage
from trp_strata.widget_engine import Controller


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        override = patch.object(storage, "CUSTOM_WIDGETS", str(self.root))
        override.start()
        self.addCleanup(override.stop)
        self.loader = layout.ComponentLoader()

    def package(self, name="counter"):
        folder = self.root / name
        folder.mkdir()
        (folder / "view.json").write_text(json.dumps({"view": {"type": "Text", "text": "Hello"}}))
        return folder

    def test_view_only_and_local_controller_packages(self):
        folder = self.package()
        self.assertIs(self.loader.load("counter").controller, Controller)
        (folder / "controller.py").write_text(
            "from trp_strata.widget_engine import Controller as Base\n"
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class Controller(Base):\n"
            "    count: int = 0\n")
        first = self.loader.load("counter")
        self.assertIsNot(first.controller, Controller)
        self.assertEqual(first.controller().count, 0)
        (folder / "view.json").write_text(json.dumps({"view": {"type": "Text", "text": "Changed"}}))
        second = self.loader.load("counter")
        self.assertIs(first.controller, second.controller)
        self.assertEqual(second.view["text"], "Changed")

    def test_invalid_or_temporarily_missing_view_keeps_last_definition(self):
        folder = self.package()
        first = self.loader.load("counter")
        (folder / "view.json").unlink()
        with self.assertLogs("trp_strata.layout", level="ERROR"):
            self.assertIs(self.loader.load("counter"), first)
        (folder / "view.json").write_text("{")
        with self.assertLogs("trp_strata.layout", level="ERROR"):
            self.assertIs(self.loader.load("counter"), first)

    def test_package_overrides_flat_json_and_builtin(self):
        folder = self.package("Clock")
        (self.root / "Clock.json").write_text(json.dumps({"view": {"type": "Text", "text": "Flat"}}))
        self.assertEqual(self.loader.load("Clock").view["text"], "Hello")
        (folder / "view.json").unlink()
        folder.rmdir()
        self.assertEqual(self.loader.load("Clock").view["text"], "Flat")
        (self.root / "Clock.json").unlink()
        self.assertEqual(self.loader.load("Clock").view["type"], "Column")

    def test_every_builtin_has_a_json_view_and_an_independent_controller_module(self):
        from trp_strata.widget_packages import DIRECTORY, PACKAGES, controllers
        from trp_strata.widget_views import definition
        registry = controllers()
        for name, (folder, alias) in PACKAGES.items():
            source = json.loads((DIRECTORY / folder / "view.json").read_text())
            self.assertNotIn("controller", source)
            loaded = definition({**source, "controller": alias}, registry)
            self.assertEqual(loaded.controller.__module__, f"trp_strata.widget_packages.{folder}.controller")
            self.assertEqual(loaded.view, self.loader.load(name).view)

    def test_copy_command_creates_loadable_package_without_overwriting(self):
        from trp_strata.cli import main
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["widget", "copy", "Notes", "my_notes"]), 0)
        folder = self.root / "my_notes"
        self.assertEqual({path.name for path in folder.iterdir()}, {"view.json", "controller.py"})
        self.assertIn("trpstrata widget add my_notes", output.getvalue())
        loaded = self.loader.load("my_notes")
        self.assertIsNot(loaded.controller, self.loader.load("Notes").controller)
        original = (folder / "view.json").read_text()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["widget", "copy", "Clock", "my_notes"]), 1)
        self.assertEqual((folder / "view.json").read_text(), original)

    def test_copy_rejects_paths_and_conflicting_flat_files(self):
        from trp_strata.widget_packages import copy_builtin
        for name in ("../escape", "bad-name", ""):
            with self.assertRaises(ValueError):
                copy_builtin("Clock", name)
        (self.root / "my_clock.json").write_text("user work")
        with self.assertRaises(ValueError):
            copy_builtin("Clock", "my_clock")
        self.assertFalse((self.root / "my_clock").exists())


if __name__ == "__main__":
    unittest.main()
