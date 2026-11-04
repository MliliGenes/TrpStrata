import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from trp_strata.native_wallpaper import NativeWallpaper


class Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class NativeWallpaperTests(unittest.TestCase):
    def test_apply_image_uses_personal_profile_and_all_native_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "poster.jpg"
            image.write_bytes(b"poster")
            values = {
                "picture-uri": "'file:///old.jpg'",
                "picture-uri-dark": "'file:///old-dark.jpg'",
                "picture-options": "'zoom'",
            }

            def runner(args, **_kwargs):
                if args[:2] == ["gsettings", "writable"]:
                    return Result(stdout="true\n")
                if args[:2] == ["gsettings", "get"]:
                    return Result(stdout=values[args[-1]] + "\n")
                if args[:2] == ["gsettings", "set"]:
                    values[args[-2]] = args[-1]
                    return Result()
                if args[:4] == ["systemctl", "--user", "is-active", "--quiet"]:
                    return Result()
                if args[:3] == ["systemctl", "--user", "show"]:
                    return Result()
                if args[:3] == ["systemctl", "--user", "daemon-reload"]:
                    return Result()
                raise AssertionError(args)

            with patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}, clear=False), \
                    patch("trp_strata.native_wallpaper.os.geteuid", return_value=1000):
                shell_loaded = NativeWallpaper(runner=runner).apply_image(image)

            self.assertIsNone(shell_loaded)
            uri = repr(image.resolve().as_uri())
            self.assertEqual(values["picture-uri"], uri)
            self.assertEqual(values["picture-uri-dark"], uri)
            self.assertEqual(values["picture-options"], "'zoom'")
            override = root / "systemd/user/org.gnome.Shell@x11.service.d/wallpaper-profile.conf"
            self.assertIn(f"DCONF_PROFILE={root / 'dconf/wallpaper-profile'}", override.read_text())


if __name__ == "__main__":
    unittest.main()
