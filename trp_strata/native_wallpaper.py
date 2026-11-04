"""Native GNOME wallpaper access through the user's personal dconf profile.

The school desktop may lock GNOME's normal wallpaper keys in its default
profile.  The existing personal profile is user-owned, so the Shell service
and trpStrata can use it without a system-wide change or an X11 wallpaper
window.  This module intentionally has no GTK dependency and must be loaded
before GSettings is initialized.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


class NativeWallpaperError(RuntimeError):
    """Raised when GNOME cannot read or write the native wallpaper keys."""


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".trpstrata-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def profile_path() -> Path:
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config / "dconf" / "wallpaper-profile"


def prepare_environment() -> Path:
    """Select the personal dconf profile before importing Gio/GSettings."""
    profile = profile_path()
    if not profile.exists():
        current = os.environ.get("DCONF_PROFILE", "user")
        source = Path(current) if current.startswith("/") else Path("/etc/dconf/profile") / current
        storage = "user-db:user"
        try:
            for line in source.read_text(encoding="utf-8").splitlines():
                if re.match(r"^\s*(user-db:|service-db:)", line):
                    storage = line.strip()
                    break
        except OSError:
            pass
        _atomic_write(profile, storage + "\n")
    if not profile.is_file():
        raise NativeWallpaperError(f"The personal GNOME profile is not readable: {profile}")
    os.environ["DCONF_PROFILE"] = str(profile)
    os.environ["GSETTINGS_BACKEND"] = "dconf"
    return profile


class NativeWallpaper:
    """Read and write GNOME's native background settings."""

    SCHEMA = "org.gnome.desktop.background"
    FITS = {"zoom", "scaled", "stretched", "centered", "wallpaper", "spanned"}

    def __init__(self, runner=None):
        self.profile = prepare_environment()
        self.config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        self.runner = runner or subprocess.run

    def _run(self, args, *, allow_failure=False):
        try:
            result = self.runner(
                args,
                capture_output=True,
                text=True,
                timeout=6,
                env={**os.environ, "DCONF_PROFILE": str(self.profile), "GSETTINGS_BACKEND": "dconf"},
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            if allow_failure:
                return None
            raise NativeWallpaperError(f"Could not access GNOME settings: {error}") from error
        if not allow_failure and (result.returncode or result.stderr.strip()):
            raise NativeWallpaperError(result.stderr.strip() or result.stdout.strip() or "GNOME rejected the change")
        return result

    def get(self, key):
        result = self._run(["gsettings", "get", self.SCHEMA, key])
        return result.stdout.strip()

    def writable(self, key):
        result = self._run(["gsettings", "writable", self.SCHEMA, key], allow_failure=True)
        return bool(result and result.returncode == 0 and not result.stderr.strip()
                    and result.stdout.strip() == "true")

    def _shell_service(self):
        kinds = [os.environ.get("XDG_SESSION_TYPE", "x11"), "x11", "wayland"]
        for kind in dict.fromkeys(kinds):
            if kind not in ("x11", "wayland"):
                continue
            unit = f"org.gnome.Shell@{kind}.service"
            result = self._run(["systemctl", "--user", "is-active", "--quiet", unit], allow_failure=True)
            if result and result.returncode == 0:
                return unit
        return None

    def _shell_loaded(self, unit):
        if not unit:
            return None
        result = self._run(["systemctl", "--user", "show", unit, "--property=MainPID", "--value"],
                           allow_failure=True)
        if not result or not result.stdout.strip().isdigit() or int(result.stdout.strip()) <= 0:
            return None
        try:
            environ = Path(f"/proc/{int(result.stdout.strip())}/environ").read_bytes().split(b"\0")
            return b"DCONF_PROFILE=" + str(self.profile).encode() in environ
        except OSError:
            return None

    def ensure_setup(self):
        """Ensure the active GNOME Shell service uses the personal profile."""
        if os.geteuid() == 0:
            raise NativeWallpaperError("Run trpStrata as your normal desktop user, not as root.")
        prepare_environment()
        if not self.writable("picture-uri"):
            raise NativeWallpaperError("GNOME's native wallpaper setting is still locked in this session.")
        unit = self._shell_service()
        if not unit:
            raise NativeWallpaperError("No active GNOME Shell user service was found.")

        override = self.config_root / "systemd/user" / (unit + ".d") / "wallpaper-profile.conf"
        if override.exists():
            text = override.read_text(encoding="utf-8")
            values = []
            for line in text.splitlines():
                if line.strip().startswith("Environment="):
                    try:
                        values.extend(shlex.split(line.strip().partition("=")[2]))
                    except ValueError:
                        continue
            expected = "DCONF_PROFILE=" + str(self.profile)
            if expected not in [value.replace("%%", "%") for value in values] and self._shell_loaded(unit) is not True:
                raise NativeWallpaperError(
                    "A different GNOME Shell profile override is active; it was left unchanged."
                )
        else:
            value = str(self.profile).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
            _atomic_write(
                override,
                f'[Service]\nEnvironment="DCONF_PROFILE={value}"\nEnvironment=GSETTINGS_BACKEND=dconf\n',
            )
            self._run(["systemctl", "--user", "daemon-reload"])

        return self._shell_loaded(unit)

    def apply_image(self, path, *, fit="zoom"):
        """Set a still image for both light and dark GNOME modes."""
        if fit not in self.FITS:
            raise NativeWallpaperError("Choose a valid wallpaper fit.")
        image = Path(path).resolve(strict=True)
        if not image.is_file():
            raise NativeWallpaperError("Choose a readable image file.")
        shell_loaded = self.ensure_setup()
        uri = image.as_uri()
        changes = [
            ("picture-uri", repr(uri)),
            ("picture-uri-dark", repr(uri)),
            ("picture-options", repr(fit)),
        ]
        previous = {}
        for key, value in changes:
            if not self.writable(key):
                raise NativeWallpaperError(f"GNOME will not change {key}.")
            previous[key] = self.get(key)

        completed = []
        try:
            for key, value in changes:
                completed.append(key)
                self._run(["gsettings", "set", self.SCHEMA, key, value])
                if ast.literal_eval(self.get(key)) != ast.literal_eval(value):
                    raise NativeWallpaperError(f"GNOME did not save {key}.")
        except (NativeWallpaperError, ValueError, SyntaxError):
            for key in reversed(completed):
                self._run(["gsettings", "set", self.SCHEMA, key, previous[key]], allow_failure=True)
            raise
        return shell_loaded

    def refresh_lock_screen(self):
        """Let Codam's optional image loader read the same personal settings."""
        unit = "codam-web-greeter.service"
        result = self._run(["systemctl", "--user", "show", unit,
                            "--property=LoadState", "--value"], allow_failure=True)
        if not result or result.returncode or result.stdout.strip() != "loaded":
            return  # Standard GNOME follows the native desktop wallpaper.
        override = self.config_root / "systemd/user" / (unit + ".d") / "trpstrata-profile.conf"
        value = str(self.profile).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
        text = f'[Service]\nEnvironment="DCONF_PROFILE={value}"\nEnvironment=GSETTINGS_BACKEND=dconf\n'
        if not override.exists() or override.read_text() != text:
            if override.exists():
                raise NativeWallpaperError(f"Conflicting greeter profile override: {override}")
            _atomic_write(override, text)
            self._run(["systemctl", "--user", "daemon-reload"])
        self._run(["systemctl", "--user", "try-restart", unit])
