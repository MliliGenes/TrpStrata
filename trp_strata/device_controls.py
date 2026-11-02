"""Volume and GNOME brightness I/O, isolated from the desktop rendering thread."""
import math
import os
import re
import shutil
import subprocess
import threading


class VolumeBackend:
    def __init__(self):
        self.command = shutil.which("pactl") or shutil.which("wpctl")
        if not self.command:
            raise RuntimeError("Volume needs pactl or wpctl installed")
        self.pulse = os.path.basename(self.command) == "pactl"

    def run(self, *args):
        result = subprocess.run([self.command, *args], capture_output=True, text=True,
                                timeout=2, env={**os.environ, "LC_ALL": "C"})
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Audio device unavailable")
        return result.stdout

    def read(self):
        if self.pulse:
            output = self.run("get-sink-volume", "@DEFAULT_SINK@")
            levels = [int(n) for n in re.findall(r"/\s*(\d+)%", output)]
            if not levels:
                raise RuntimeError("Cannot read output volume")
            value = round(sum(levels) / len(levels))
            muted = self.run("get-sink-mute", "@DEFAULT_SINK@").strip().endswith("yes")
        else:
            output = self.run("get-volume", "@DEFAULT_AUDIO_SINK@")
            match = re.search(r"Volume:\s*([\d.]+)", output)
            if not match:
                raise RuntimeError("Cannot read output volume")
            value, muted = round(float(match[1]) * 100), "[MUTED]" in output
        return min(100, max(0, value)), muted

    def set_value(self, value):
        self.run("set-sink-volume" if self.pulse else "set-volume",
                 "@DEFAULT_SINK@" if self.pulse else "@DEFAULT_AUDIO_SINK@", f"{value}%")

    def set_muted(self, muted):
        self.run("set-sink-mute" if self.pulse else "set-mute",
                 "@DEFAULT_SINK@" if self.pulse else "@DEFAULT_AUDIO_SINK@", "1" if muted else "0")


class BrightnessBackend:
    def __init__(self):
        from gi.repository import Gio, GLib
        self.Gio, self.GLib = Gio, GLib
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def call(self, method, signature, args):
        return self.bus.call_sync("org.gnome.SettingsDaemon.Power", "/org/gnome/SettingsDaemon/Power",
                                  "org.freedesktop.DBus.Properties", method,
                                  self.GLib.Variant(signature, args), None,
                                  self.Gio.DBusCallFlags.NONE, 1500, None)

    def read(self):
        value = self.call("Get", "(ss)", ("org.gnome.SettingsDaemon.Power.Screen", "Brightness")).unpack()[0]
        if not 0 <= value <= 100:
            raise RuntimeError("This display does not expose brightness through GNOME")
        return value, False

    def set_value(self, value):
        self.call("Set", "(ssv)", ("org.gnome.SettingsDaemon.Power.Screen", "Brightness",
                                  self.GLib.Variant("i", value)))


class DeviceModel:
    """Poll external changes and coalesce slider writes; callbacks never block GTK."""
    def __init__(self, factory):
        self.factory = factory
        self.condition = threading.Condition()
        self.closed = False
        self.pending = {}
        self.revision = 0
        self.value, self.muted, self.available, self.error = 0, False, False, "Connecting…"
        self.thread = threading.Thread(target=self._run, daemon=True, name="device-control")
        self.thread.start()

    def view(self):
        with self.condition:
            return self.value, self.muted, self.available, self.error

    def set_value(self, value):
        if not math.isfinite(float(value)) or not 0 <= value <= 100:
            raise ValueError("Value must be between 0 and 100")
        with self.condition:
            self.value = round(value)
            self.pending["value"] = self.value
            self.revision += 1
            self.condition.notify_all()

    def toggle_mute(self):
        with self.condition:
            self.muted = not self.muted
            self.pending["muted"] = self.muted
            self.revision += 1
            self.condition.notify_all()

    def _run(self):
        backend = None
        while True:
            with self.condition:
                if self.closed:
                    return
                commands, self.pending = self.pending, {}
                revision = self.revision
            try:
                if backend is None:
                    backend = self.factory()
                if "value" in commands:
                    backend.set_value(commands["value"])
                if "muted" in commands:
                    backend.set_muted(commands["muted"])
                value, muted = backend.read()
                with self.condition:
                    if revision == self.revision:
                        self.value, self.muted = value, muted
                    self.available, self.error = True, ""
            except Exception as error:
                with self.condition:
                    self.available, self.error = False, str(error)
                backend = None
            with self.condition:
                self.condition.notify_all()
                self.condition.wait_for(lambda: self.closed or self.pending, timeout=1)
                if self.pending and not self.closed:
                    # Small bounded window batches drag events without delaying rendering.
                    self.condition.wait(timeout=.06)

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
