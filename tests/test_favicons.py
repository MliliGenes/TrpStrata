import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock

from trp_strata.favicons import FaviconModel, IconLinks, load_favicon, site_origin


class FaviconTests(unittest.TestCase):
    def test_origin_drops_credentials_path_and_query(self):
        self.assertEqual(site_origin("https://name:password@example.com:8443/private?token=secret#x"),
                         "https://example.com:8443/")
        self.assertEqual(site_origin("http://[::1]:8080/a"), "http://[::1]:8080/")

    def test_discovery_recognizes_shortcut_and_apple_icons(self):
        parser = IconLinks()
        parser.feed('<link rel="stylesheet" href="style.css"><link rel="shortcut ICON" href="/icon.ico">'
                    '<link rel="apple-touch-icon" href="/apple.png">')
        self.assertEqual(parser.links, ["/icon.ico", "/apple.png"])

    def test_relative_icon_resolution_and_persistent_cache(self):
        fetch = Mock(side_effect=[(b'<link rel="icon" href="icons/brand.png">', "https://example.com/home/"),
                                  (b"image", "https://example.com/home/icons/brand.png")])
        with tempfile.TemporaryDirectory() as root:
            path = load_favicon("https://example.com/", root, fetch=fetch, encode=lambda data: b"PNG:" + data)
            self.assertEqual(Path(path).read_bytes(), b"PNG:image")
            self.assertEqual(fetch.call_args.args[0], "https://example.com/home/icons/brand.png")
            fetch.reset_mock(side_effect=True)
            self.assertEqual(load_favicon("https://example.com/", root, fetch=fetch), path)
            fetch.assert_not_called()

    def test_bad_icons_fall_back_and_expired_cache_survives_network_failure(self):
        fetch = Mock(side_effect=[(b'<link rel="icon" href="file:///private"><link rel="icon" href="/broken">',
                                  "https://example.com/"),
                                 (b"bad image", "https://example.com/broken"),
                                 (b"good image", "https://example.com/favicon.ico")])
        def encode(data):
            if data == b"bad image":
                raise ValueError("Invalid image")
            return b"PNG"
        with tempfile.TemporaryDirectory() as root:
            path = load_favicon("https://example.com/", root, fetch=fetch, encode=encode)
            self.assertIsNotNone(path)
            self.assertEqual(fetch.call_args.args[0], "https://example.com/favicon.ico")
            metadata = next(Path(root).glob("*.json"))
            os.utime(metadata, (0, 0))
            self.assertEqual(load_favicon("https://example.com/", root,
                                         fetch=Mock(side_effect=OSError("offline"))), path)

    def test_background_deduplicates_same_site_and_refreshes_icon(self):
        started, release = threading.Event(), threading.Event()
        def fetch(origin):
            started.set()
            release.wait(2)
            return "/cache/site.png"
        fetcher = Mock(side_effect=fetch)
        model = FaviconModel(fetcher)
        try:
            self.assertEqual(model.icon("https://example.com/one"), "web-browser")
            self.assertTrue(started.wait(2))
            self.assertEqual(model.icon("https://example.com/two"), "web-browser")
            release.set()
            with model.condition:
                self.assertTrue(model.condition.wait_for(lambda: not model.entries["https://example.com/"][2], timeout=3))
            self.assertEqual(model.icon("https://example.com/three"), "/cache/site.png")
            fetcher.assert_called_once_with("https://example.com/")
        finally:
            release.set()
            model.close()
            model.thread.join(3)
        self.assertFalse(model.thread.is_alive())

    def test_failed_lookup_is_not_retried_every_frame(self):
        fetch = Mock(return_value=None)
        model = FaviconModel(fetch)
        try:
            model.icon("https://example.com")
            with model.condition:
                self.assertTrue(model.condition.wait_for(lambda: not model.entries["https://example.com/"][2], timeout=3))
            self.assertEqual(model.icon("https://example.com"), "web-browser")
            fetch.assert_called_once()
        finally:
            model.close()
            model.thread.join(3)


if __name__ == "__main__":
    unittest.main()
