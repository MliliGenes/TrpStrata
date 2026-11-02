import configparser
from contextlib import ExitStack, nullcontext
import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch

from trp_strata import palette, system_theme


class SystemThemeTests(unittest.TestCase):
    def test_folder_overlay_is_valid_and_preserves_base_theme(self):
        for p in palette.build([(210, .8, .5)] * 100).values():
            with tempfile.TemporaryDirectory() as root:
                system_theme.write_icons(root, "trpStrata A", "Yaru", p)
                index = configparser.ConfigParser()
                index.read(os.path.join(root, "index.theme"))
                self.assertEqual(index["Icon Theme"]["Inherits"], "Yaru,hicolor")
                for name in system_theme.FOLDERS:
                    tree = ET.parse(os.path.join(root, "scalable", "places", name + ".svg"))
                    self.assertEqual(tree.find(".//*[@id='folder-front']").get("fill"), p["accent"])
                self.assertEqual(index["scalable/mimetypes"]["Context"], "MimeTypes")
                for names in system_theme.FILE_GROUPS.values():
                    for name in names:
                        tree = ET.parse(os.path.join(root, "scalable", "mimetypes", name + ".svg"))
                        self.assertEqual(tree.find(".//*[@id='file-paper']").get("fill"), p["sheet"])


class SystemThemeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from trp_strata import core
        except ImportError:
            raise unittest.SkipTest("Gio unavailable; use /usr/bin/python3")
        cls.core = core

    def test_upgrade_keeps_originals_and_adds_new_settings_once(self):
        core = self.core
        old = {"org.gnome.desktop.interface gtk-theme": "'Old GTK'",
               "terminal-default": "'original-terminal'", "terminal-list": "[]"}
        settings = Mock()
        settings.list_keys.return_value = ["gtk-theme", "icon-theme"]
        settings.get_value.return_value = core.GLib.Variant("s", "Yaru")
        with tempfile.TemporaryDirectory() as root, \
                patch.object(core, "ORIGINALS", os.path.join(root, "originals.json")), \
                patch.object(core, "_settings", return_value=settings), \
                patch.object(core, "_dconf") as dconf:
            core._write(core.ORIGINALS, json.dumps(old))
            core._save_originals()
            settings.get_value.return_value = core.GLib.Variant("s", core.OUR_THEMES[0])
            core._save_originals()
            saved = core._read_json(core.ORIGINALS, {})
            self.assertEqual(saved["org.gnome.desktop.interface icon-theme"], "'Yaru'")
            for key, value in old.items():
                self.assertEqual(saved[key], value)
            dconf.assert_not_called()

    def test_recolour_flips_icons_and_shell_without_inheritance_cycle(self):
        core = self.core
        settings = Mock()
        settings.get_string.return_value = core.OUR_THEMES[0]
        p = palette.build([(20, .8, .5)])["dark"]
        with patch.object(core, "_settings", return_value=settings), \
                patch.object(core, "_read_json", return_value={
                    "org.gnome.desktop.interface icon-theme": "'Yaru'"}), \
                patch.object(system_theme, "write_icons") as icons, \
                patch.object(core, "_set") as setting:
            core._apply_system_theme(p)
            self.assertTrue(all(call.args[2] == "Yaru" for call in icons.call_args_list))
            values = {(call.args[0], call.args[1]): call.args[2].unpack()
                      for call in setting.call_args_list}
            self.assertEqual(values[("org.gnome.desktop.interface", "icon-theme")], core.OUR_THEMES[1])
            self.assertEqual(values[(system_theme.SHELL_SCHEMA, "name")], core.OUR_THEMES[1])
            self.assertEqual(values[(system_theme.DOCK_SCHEMA, "background-color")], p["paper"])

    def test_missing_shell_and_dock_do_not_block_icons(self):
        core = self.core
        interface = Mock()
        interface.get_string.return_value = "Adwaita"
        with patch.object(core, "_settings", side_effect=lambda schema:
                          interface if schema == "org.gnome.desktop.interface" else None), \
                patch.object(core, "_read_json", return_value={}), \
                patch.object(system_theme, "write_icons"), \
                patch.object(core, "_set") as setting:
            core._apply_system_theme(palette.build([])["light"])
            self.assertNotIn(system_theme.SHELL_SCHEMA, [call.args[0] for call in setting.call_args_list])

    def test_restore_returns_system_settings_and_removes_generated_icons(self):
        core = self.core
        saved = {"org.gnome.desktop.interface icon-theme": "'Yaru'",
                 f"{system_theme.SHELL_SCHEMA} name": "'My Shell'",
                 f"{system_theme.DOCK_SCHEMA} custom-background-color": "false",
                 f"{system_theme.DOCK_SCHEMA} background-color": "'#123456'"}
        with tempfile.TemporaryDirectory() as root, ExitStack() as stack:
            for key in ("HOME", "CONFIG_DIR", "THEMES_DIR", "ICONS_DIR"):
                stack.enter_context(patch.object(core, key, os.path.join(root, key)))
            for key in ("ORIGINALS", "AWAKE", "THEME_CSS"):
                stack.enter_context(patch.object(core, key, os.path.join(root, key)))
            for key in ("save_config", "_save_state", "_reload_gtk"):
                stack.enter_context(patch.object(core, key))
            stack.enter_context(patch.object(core, "locked", return_value=nullcontext()))
            stack.enter_context(patch.object(core.Gio.Settings, "new", return_value=Mock(
                get_string=Mock(return_value="Adwaita"))))
            stack.enter_context(patch.object(core.Gio.Settings, "sync"))
            setting = stack.enter_context(patch.object(core, "_set"))
            core._write(core.ORIGINALS, json.dumps(saved))
            for name in core.OUR_THEMES:
                os.makedirs(os.path.join(core.ICONS_DIR, name))
            core.restore()
            values = {f"{call.args[0]} {call.args[1]}": call.args[2].unpack()
                      for call in setting.call_args_list}
            self.assertEqual(values["org.gnome.desktop.interface icon-theme"], "Yaru")
            self.assertEqual(values[f"{system_theme.SHELL_SCHEMA} name"], "My Shell")
            self.assertFalse(values[f"{system_theme.DOCK_SCHEMA} custom-background-color"])
            self.assertEqual(values[f"{system_theme.DOCK_SCHEMA} background-color"], "#123456")
            self.assertFalse(os.path.exists(core.ORIGINALS))
            self.assertEqual(os.listdir(core.ICONS_DIR), [])


if __name__ == "__main__":
    unittest.main()
