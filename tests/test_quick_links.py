import unittest
from unittest.mock import Mock

from trp_strata.components import component_scope, resolve
from trp_strata.quick_links import QuickLinksModel, normalize_links
from trp_strata.widgets.quick_links import QuickLinks


class QuickLinksTests(unittest.TestCase):
    def test_normalize_preserves_order_paths_queries_and_fragments(self):
        links = [{"label": " Docs ", "url": " example.com/docs?q=one#top "},
                 {"label": "Intranet", "url": "http://localhost:8080/"}]
        self.assertEqual(normalize_links(links), [
            {"label": "Docs", "url": "https://example.com/docs?q=one#top"}, links[1]])
        self.assertEqual(links[0]["label"], " Docs ")
        self.assertEqual(normalize_links([]), [])

    def test_invalid_addresses_and_missing_labels_are_rejected(self):
        for url in ("", "https://", "https://host:bad", "https://host:70000", "file:///etc/passwd",
                    "javascript:alert(1)", "https://exa mple.com", "https://[bad"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize_links([{"label": "Link", "url": url}])
        for links in ("url", [None], [{"label": "", "url": "https://example.com"}]):
            with self.assertRaises(ValueError):
                normalize_links(links)

    def test_each_button_opens_its_own_url(self):
        opener = Mock()
        favicons = Mock(icon=Mock(return_value="/tmp/example.png"))
        model = QuickLinksModel(opener=opener, favicons=favicons)
        links = [{"label": "Same label", "url": "https://example.com/one"},
                 {"label": "Same label", "url": "https://example.com/two"}]
        with component_scope({"quick-links": model}):
            tree = resolve(QuickLinks(config={}, links=links))
        buttons = [child for child in tree.children if child.kind == "button"]
        for button, link in zip(buttons, links):
            self.assertEqual(button.props["system_icon"], "/tmp/example.png")
            button.props["on_click"]()
            opener.assert_called_with(link["url"])
        self.assertEqual(len(buttons), 2)
        model.close()
        favicons.close.assert_called_once()

    def test_browser_error_is_visible_and_success_clears_it(self):
        opener = Mock(side_effect=RuntimeError("No browser"))
        model = QuickLinksModel(opener=opener)
        model.launch("Docs", "https://example.com")
        self.assertIn("No browser", model.status)
        opener.side_effect = None
        model.launch("Docs", "https://example.com")
        self.assertEqual(model.status, "")


if __name__ == "__main__":
    unittest.main()
