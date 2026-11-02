import unittest
from unittest.mock import Mock

from trp_strata.launcher import LauncherModel
from trp_strata.components import component_scope, resolve
from trp_strata.widgets.launcher import Launcher


def application(app_id, name, visible=True):
    app = Mock()
    app.get_id.return_value = app_id
    app.get_display_name.return_value = name
    app.get_description.return_value = "Open " + name
    app.get_icon.return_value = None
    app.should_show.return_value = visible
    return app


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.browser = application("browser.desktop", "Browser")
        self.files = application("files.desktop", "Files")
        self.hidden = application("hidden.desktop", "Hidden", False)
        self.backend = Mock()
        self.backend.applications.return_value = [self.files, self.hidden, self.browser]
        self.backend.favourites.return_value = ["files.desktop", "gone.desktop", "hidden.desktop", "browser.desktop"]
        self.model = LauncherModel(lambda changed: self.backend)

    def test_favourites_keep_order_and_filter_unavailable_or_hidden_apps(self):
        entries, pages, all_apps = self.model.view()
        self.assertEqual(entries, [self.files, self.browser])
        self.assertEqual((pages, all_apps), (1, False))
        self.model.view()
        self.backend.applications.assert_called_once()

    def test_all_apps_sort_page_and_clamp_after_uninstall(self):
        self.backend.favourites.return_value = []
        self.assertEqual(self.model.view(page_size=1), ([self.browser], 2, True))
        self.model.move(1)
        self.assertEqual(self.model.view(page_size=1), ([self.files], 2, True))
        self.backend.applications.return_value = [self.browser]
        self.model.invalidate()
        self.assertEqual(self.model.view(page_size=1), ([self.browser], 1, True))
        self.assertEqual(self.model.page, 0)

    def test_empty_favourites_fall_back_to_all_but_explicit_empty_pins_do_not(self):
        self.backend.favourites.return_value = []
        self.assertEqual(self.model.view()[0], [self.browser, self.files])
        self.assertEqual(self.model.view(apps=[]), ([], 1, False))
        self.assertEqual(self.model.view(apps=["files.desktop"])[0], [self.files])

    def test_launch_errors_are_visible_and_backend_is_closed(self):
        self.model.view()
        self.model.launch("files.desktop")
        self.backend.launch.assert_called_once_with(self.files)
        self.backend.launch.side_effect = RuntimeError("Not installed")
        self.model.launch("browser.desktop")
        self.assertIn("Could not open Browser", self.model.status)
        self.assertIn("Not installed", self.model.status)
        self.model.launch("gone.desktop")
        self.assertEqual(self.model.status, "Application no longer available.")
        self.model.close()
        self.backend.close.assert_called_once()

    def test_component_buttons_launch_their_own_app(self):
        with component_scope({"launcher": self.model}):
            tree = resolve(Launcher(config={}))
        rows = tree.children[2].children
        self.assertTrue(all(len(row.children) == 3 and row.props["homogeneous"] for row in rows))
        buttons = [cell for row in rows for cell in row.children if cell.kind == "button"]
        self.assertEqual([button.props["text"] for button in buttons], ["Files", "Browser"])
        for button, app in zip(buttons, (self.files, self.browser)):
            button.props["on_click"]()
            self.backend.launch.assert_called_with(app)

    def test_component_uses_serialized_app_icon_and_missing_icon_fallback(self):
        self.browser.get_icon.return_value = Mock(to_string=Mock(return_value="web-browser"))
        with component_scope({"launcher": self.model}):
            tree = resolve(Launcher(config={}))
        buttons = [cell for row in tree.children[2].children for cell in row.children if cell.kind == "button"]
        self.assertEqual(buttons[0].props["system_icon"], "application-x-executable")
        self.assertEqual(buttons[1].props["system_icon"], "web-browser")
        self.assertIn("Browser", buttons[1].props["tooltip"])

    def test_invalid_props_do_not_launch_anything(self):
        for props in ({"apps": "files.desktop"}, {"apps": [123]}, {"apps": ["echo hi"]},
                      {"page_size": 0}, {"page_size": True}, {"page_size": 21}):
            with self.subTest(props=props), self.assertRaises(ValueError):
                self.model.view(**props)
        self.backend.launch.assert_not_called()

    def test_search_finds_unpinned_apps_and_clearing_restores_favourites(self):
        self.backend.favourites.return_value = ["files.desktop"]
        self.model.set_query("  BROWSER ")
        self.assertEqual(self.model.view()[0], [self.browser])
        self.model.set_query("no match")
        self.assertEqual(self.model.view()[0], [])
        self.model.set_query("")
        self.assertEqual(self.model.view()[0], [self.files])
        self.assertEqual(self.model.page, 0)


if __name__ == "__main__":
    unittest.main()
