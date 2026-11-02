import threading
import unittest
from unittest.mock import Mock, patch

from trp_strata.components import Slider
from trp_strata.device_controls import DeviceModel, VolumeBackend


class DeviceControlsTests(unittest.TestCase):
    def model(self, factory):
        model = DeviceModel(factory)
        def cleanup():
            model.close()
            model.thread.join(3)
        self.addCleanup(cleanup)
        return model

    def wait(self, model, predicate):
        with model.condition:
            self.assertTrue(model.condition.wait_for(predicate, timeout=3))

    def test_pactl_reads_channels_mute_and_writes_default_device(self):
        with patch("trp_strata.device_controls.shutil.which", return_value="/usr/bin/pactl"):
            backend = VolumeBackend()
        backend.run = Mock(side_effect=["Volume: front-left: 32768 / 50% / -18 dB, front-right: 32768 / 50% / -18 dB", "Mute: yes"])
        self.assertEqual(backend.read(), (50, True))
        backend.run = Mock()
        backend.set_value(37)
        backend.run.assert_called_with("set-sink-volume", "@DEFAULT_SINK@", "37%")
        backend.set_muted(False)
        backend.run.assert_called_with("set-sink-mute", "@DEFAULT_SINK@", "0")

    def test_wpctl_fallback(self):
        with patch("trp_strata.device_controls.shutil.which", side_effect=[None, "/usr/bin/wpctl"]):
            backend = VolumeBackend()
        backend.run = Mock(return_value="Volume: 0.42 [MUTED]")
        self.assertEqual(backend.read(), (42, True))
        backend.set_value(70)
        backend.run.assert_called_with("set-volume", "@DEFAULT_AUDIO_SINK@", "70%")

    def test_poll_tracks_external_changes_and_mute(self):
        backend = Mock()
        backend.read.return_value = (30, False)
        model = self.model(lambda: backend)
        self.wait(model, lambda: model.available)
        backend.read.return_value = (65, True)
        self.wait(model, lambda: model.value == 65 and model.muted)
        backend.read.return_value = (65, False)
        model.toggle_mute()
        self.wait(model, lambda: backend.set_muted.called)
        backend.set_muted.assert_called_with(False)

    def test_drag_keeps_latest_value_while_backend_read_is_pending(self):
        started, release = threading.Event(), threading.Event()
        backend = Mock()
        def read():
            started.set()
            release.wait(2)
            return (backend.set_value.call_args.args[0] if backend.set_value.called else 20), False
        backend.read.side_effect = read
        model = self.model(lambda: backend)
        try:
            self.assertTrue(started.wait(2))
            for value in (35, 50, 81):
                model.set_value(value)
            self.assertEqual(model.view()[0], 81)
        finally:
            release.set()
        self.wait(model, lambda: backend.set_value.called)
        backend.set_value.assert_called_once_with(81)

    def test_unavailable_device_reports_error_and_recovers(self):
        backend = Mock()
        backend.read.side_effect = RuntimeError("No supported display")
        model = self.model(lambda: backend)
        self.wait(model, lambda: "No supported display" in model.error)
        self.assertFalse(model.available)
        backend.read.side_effect = None
        backend.read.return_value = (40, False)
        self.wait(model, lambda: model.available)
        self.assertEqual(model.view(), (40, False, True, ""))

    def test_slider_validation(self):
        for value in (-1, 101, float("nan")):
            with self.assertRaises(ValueError):
                Slider(value, label="Volume", on_change=lambda _v: None)


if __name__ == "__main__":
    unittest.main()
