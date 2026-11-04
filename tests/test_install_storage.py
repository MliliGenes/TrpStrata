import json
import os
from pathlib import Path
import re
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from trp_strata import install_storage
from trp_strata.paths import paths_for


class StorageMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        (self.home / "goinfre").mkdir(parents=True)
        self.paths = paths_for(str(self.home), {})
        self.source = self.root / "checkout"
        (self.source / "trp_strata").mkdir(parents=True)
        (self.source / "trp_strata" / "__init__.py").write_text("# version 1\n")
        (self.source / "wallpapers").mkdir()
        (self.source / "wallpapers" / "example.jpg").write_bytes(b"wallpaper fixture")
        (self.source / "trpstrata").write_text("#!/usr/bin/env python3\nprint('fixture')\n")
        (self.source / "trpstrata").chmod(0o755)
        (self.source / "uninstall.sh").write_text("#!/bin/bash\n# uninstall fixture\n")

    def test_existing_home_data_moves_to_goinfre_and_links_keep_old_paths_working(self):
        old_app = Path(self.paths.install_link)
        old_app.mkdir(parents=True)
        (old_app / "legacy.py").write_text("old app")
        cache = Path(self.paths.cache_link)
        (cache / "frames").mkdir(parents=True)
        (cache / "frames" / "video.jpg").write_bytes(b"cached poster")
        theme = Path(self.paths.theme_links) / "adw-gtk3"
        theme.mkdir(parents=True)
        (theme / "gtk.css").write_text("theme")
        config = self.home / ".config/trpstrata/originals.json"
        config.parent.mkdir(parents=True)
        config.write_text('{"original":"settings"}')

        install_storage.install(self.source, self.paths, sys.executable)
        self.assertTrue(old_app.is_symlink())
        self.assertTrue(cache.is_symlink())
        self.assertTrue(theme.is_symlink())
        self.assertEqual((cache / "frames/video.jpg").read_bytes(), b"cached poster")
        self.assertEqual((old_app / "wallpapers/example.jpg").read_bytes(), b"wallpaper fixture")
        self.assertEqual(config.read_text(), '{"original":"settings"}')
        self.assertEqual((Path(self.paths.app) / "trpstrata").read_text().splitlines()[0], f"#!{sys.executable}")
        self.assertEqual((old_app / "uninstall.sh").read_text(), (self.source / "uninstall.sh").read_text())

        (self.source / "trp_strata/__init__.py").write_text("# version 2\n")
        install_storage.install(self.source, self.paths, sys.executable)
        self.assertEqual((old_app / "trp_strata/__init__.py").read_text(), "# version 2\n")
        self.assertEqual((cache / "frames/video.jpg").read_bytes(), b"cached poster")
        self.assertFalse(list(old_app.parent.glob(".trpstrata-previous-*")))

    def test_symlink_publish_failure_preserves_the_original_home_directory(self):
        source = self.home / ".cache/trpstrata"
        source.mkdir(parents=True)
        (source / "keep.txt").write_text("keep me")
        with patch("trp_strata.install_storage.os.replace", side_effect=OSError("fixture failure")):
            with self.assertRaises(OSError):
                install_storage.migrate_directory(source, self.paths.cache)
        self.assertTrue(source.is_dir())
        self.assertFalse(source.is_symlink())
        self.assertEqual((source / "keep.txt").read_text(), "keep me")

    def test_uninstall_removes_app_and_cache_but_keeps_shared_themes_and_other_goinfre_data(self):
        install_storage.install(self.source, self.paths, sys.executable)
        other = self.home / "goinfre/another-project"
        other.write_text("unrelated")
        theme = Path(self.paths.themes) / "adw-gtk3"
        theme.mkdir(parents=True)
        (theme / "theme.css").write_text("shared theme")
        install_storage.link_themes(self.paths)
        install_storage.uninstall(self.paths)
        self.assertFalse(Path(self.paths.app).exists())
        self.assertFalse(Path(self.paths.install_link).is_symlink())
        self.assertFalse(Path(self.paths.cache).exists())
        self.assertEqual(other.read_text(), "unrelated")
        self.assertTrue(theme.exists())

    def test_no_goinfre_uses_standard_paths_and_xdg_cache_override_is_respected(self):
        ordinary_home = self.root / "ordinary-home"
        ordinary_home.mkdir()
        paths = paths_for(str(ordinary_home), {})
        self.assertIsNone(paths.bulk)
        self.assertEqual(paths.app, paths.install_link)
        self.assertEqual(paths.cache, paths.cache_link)
        overridden = paths_for(str(self.home), {"XDG_CACHE_HOME": str(self.root / "custom-cache")})
        self.assertEqual(overridden.cache, str(self.root / "custom-cache/trpstrata"))

    def test_helper_matching_covers_canonical_and_physical_install_locations(self):
        install_storage.install(self.source, self.paths, sys.executable)
        pattern = install_storage.helper_pattern(self.paths)
        for root in (self.paths.install_link, self.paths.app, str(Path(self.paths.app).resolve())):
            self.assertRegex(f"/usr/bin/python3 {root}/trpstrata desktop", pattern)
        self.assertIsNone(re.search(pattern, "/usr/bin/python3 /tmp/unrelated/trpstrata desktop"))
        result = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
        self.assertIn(result.returncode, (0, 1), result.stderr)


if __name__ == "__main__":
    unittest.main()
