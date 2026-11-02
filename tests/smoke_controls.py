"""Manual GTK 4 check for independent widget switches; uses isolated temporary settings."""
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory() as directory:
        os.environ["XDG_CONFIG_HOME"] = directory
        os.environ["XDG_CACHE_HOME"] = directory
        os.environ["GSETTINGS_BACKEND"] = "memory"
        from trp_strata import app, layout, settings, styles
        from gi.repository import Adw, Gdk, Gio, GLib, Gtk
        if not Gtk.init_check():
            raise SystemExit("Run this check with a GTK 4 display")
        Adw.init()
        css_errors = []
        provider = Gtk.CssProvider()
        provider.connect("parsing-error", lambda _provider, _section, error: css_errors.append(str(error)))
        provider.load_from_path(str(styles.DIRECTORY / "app.css"))
        assert not css_errors, css_errors
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        styles.ensure_user_styles()
        application = Adw.Application(application_id="io.github.TrpStrata.ControlsSmoke", flags=Gio.ApplicationFlags.NON_UNIQUE)
        application.register(None)

        def wait(predicate):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                while GLib.MainContext.default().pending():
                    GLib.MainContext.default().iteration(False)
                if predicate():
                    return
                time.sleep(.02)
            raise AssertionError("Timed out waiting for the control panel to update")

        with patch.object(app.Window, "load_library"), patch.object(app.core, "start_helper"):
            window = app.Window(application)
            try:
                window.pages.set_transition_duration(0)
                window.present()
                assert set(window.section_pages) == {"wallpaper", "appearance", "widgets", "screen", "tools"}
                assert window.sidebar.get_stack() is window.pages
                assert window.pages.get_visible_child_name() == "wallpaper"
                for widget, section in ((window.hero, "wallpaper"), (window.rotation_combo, "wallpaper"),
                                        (window.palettes, "appearance"), (window.mode_row, "appearance"),
                                        (window.widget_rows, "widgets"), (window.awake_row, "screen")):
                    assert widget.is_ancestor(window.section_pages[section])
                with patch.object(app.core, "save_config", wraps=app.core.save_config) as save:
                    for name in window.section_pages:
                        window.pages.set_visible_child_name(name)
                        assert window.section_title.get_subtitle() == name.title()
                    save.assert_not_called()
                window.pages.set_visible_child_name("widgets")
                adjustment = window.section_pages["widgets"].get_vadjustment()
                wait(lambda: adjustment.get_upper() > adjustment.get_page_size() + 50)
                adjustment.set_value(40)
                window.logtime_entries["logtime_username"].set_text("unsaved-draft")
                window.pages.set_visible_child_name("appearance")
                window.pages.set_visible_child_name("widgets")
                assert window.logtime_entries["logtime_username"].get_text() == "unsaved-draft"
                assert adjustment.get_value() == 40
                window.navigation.set_fold_policy(Adw.FlapFoldPolicy.ALWAYS)
                wait(lambda: window.navigation.get_folded())
                window.sidebar_toggle.set_active(True)
                assert window.navigation.get_reveal_flap()
                window.pages.set_visible_child_name("screen")
                assert not window.navigation.get_reveal_flap()
                assert not window.sidebar_toggle.get_active()
                window.navigation.set_fold_policy(Adw.FlapFoldPolicy.AUTO)
                window.pages.set_visible_child_name("widgets")
                assert set(window.widget_toggles) == {"clock", "calendar", "system", "cleaner", "notes", "logtime", "now-playing", "launcher", "file-search", "quick-links", "volume", "brightness"}
                for preset in window.font_keys:
                    window.font_combo.set_selected(window.font_keys.index(preset))
                    wait(lambda: settings.load_config()["widget_font"] == preset)
                app.core.save_config(widget_font="mono")
                with patch.object(app.core, "save_config", wraps=app.core.save_config) as save:
                    window.sync_from_disk()
                    assert window.font_keys[window.font_combo.get_selected()] == "mono"
                    save.assert_not_called()
                assert "quick-links" in window.link_edit_buttons
                editor = window.edit_quick_links("quick-links")
                editor.title_entry.set_text("Work links")
                editor.add_link("Docs", "example.com/docs")
                # Remove the starter Intra shortcut using the real Remove button.
                first_row = editor.link_entries[0][0]
                first_row.get_first_child().get_last_child().emit("clicked")
                editor.response(Gtk.ResponseType.ACCEPT)
                wait(lambda: next(p for p in layout.load_layout() if p.id == "quick-links").props.get("title") == "Work links")
                links = next(p for p in layout.load_layout() if p.id == "quick-links").props["links"]
                assert links == [{"label": "GitHub", "url": "https://github.com"}, {"label": "Docs", "url": "https://example.com/docs"}]
                editor = window.edit_quick_links("quick-links")
                editor.add_link("Invalid", "")
                editor.response(Gtk.ResponseType.ACCEPT)
                assert editor.get_visible()
                editor.response(Gtk.ResponseType.CANCEL)
                assert next(p for p in layout.load_layout() if p.id == "quick-links").props["links"] == links
                assert "notes" in window.note_edit_buttons
                editor = window.edit_note("notes")
                editor.title_entry.set_text("My note")
                editor.text_buffer.set_text("First line\nSecond line 📝")
                editor.response(Gtk.ResponseType.ACCEPT)
                wait(lambda: next(p for p in layout.load_layout() if p.id == "notes").props.get("text") == "First line\nSecond line 📝")
                editor = window.edit_note("notes")
                assert editor.title_entry.get_text() == "My note"
                editor.text_buffer.set_text("Discard this")
                editor.response(Gtk.ResponseType.CANCEL)
                assert next(p for p in layout.load_layout() if p.id == "notes").props["text"] == "First line\nSecond line 📝"
                window.widget_toggles["launcher"].set_active(True)
                wait(lambda: next(p for p in layout.load_layout() if p.id == "launcher").enabled)
                window.widget_toggles["now-playing"].set_active(False)
                wait(lambda: not next(p for p in layout.load_layout() if p.id == "now-playing").enabled)
                window.widget_toggles["now-playing"].set_active(True)
                wait(lambda: next(p for p in layout.load_layout() if p.id == "now-playing").enabled)
                window.switches["layout_grid"].set_active(False)
                wait(lambda: not settings.load_config()["layout_grid"])
                window.grid_spins["layout_grid_size"].set_value(48)
                window.grid_spins["layout_grid_gap"].set_value(12)
                wait(lambda: settings.load_config()["layout_grid_size"] == 48)
                wait(lambda: settings.load_config()["layout_grid_gap"] == 12)
                window.logtime_entries["logtime_username"].set_text("sel-mlil")
                window.logtime_entries["logtime_goal"].set_text("196")
                window.save_logtime()
                assert settings.load_config()["logtime_username"] == "sel-mlil"
                assert settings.load_config()["logtime_goal"] == 196
                window.widget_toggles["logtime"].set_active(False)
                wait(lambda: not next(p for p in layout.load_layout() if p.id == "logtime").enabled)
                assert window.widget_toggles["calendar"].get_active()
                window.widget_toggles["calendar"].set_active(False)
                wait(lambda: not layout.load_layout()[1].enabled)
                wait(lambda: not window.widget_toggles["calendar"].get_active())
                assert window.widget_toggles["system"].get_active()
                assert window.widget_toggles["notes"].get_active()
                window.widget_toggles["clock"].set_active(False)
                wait(lambda: not layout.load_layout()[0].enabled)
                assert layout.load_layout()[2].enabled
                window.widget_toggles["calendar"].set_active(True)
                wait(lambda: layout.load_layout()[1].enabled)
                assert not layout.load_layout()[0].enabled
                assert window.blur_scale.get_value() == settings.load_config()["widget_blur_radius"]
                for radius in (0, 64, 32):
                    window.blur_scale.set_value(radius)
                    wait(lambda: settings.load_config()["widget_blur_radius"] == radius)
                settings.save_config(widget_blur_radius=17)
                with patch.object(app.core, "save_config", wraps=app.core.save_config) as save:
                    window.sync_from_disk()
                    assert window.blur_scale.get_value() == 17
                    save.assert_not_called()
                window.switches["widget_blur"].set_active(False)
                wait(lambda: settings.load_config()["widget_blur"] is False)
                assert not window.blur_scale.get_sensitive()
                assert settings.load_config()["widget_blur_radius"] == 17
                window.switches["widget_blur"].set_active(True)
                wait(lambda: settings.load_config()["widget_blur"] is True)
                assert window.blur_scale.get_sensitive()
                assert window.blur_scale.get_value() == 17
            finally:
                window.widget_pool.shutdown(wait=True)
                window.pool.shutdown(wait=True)
                window.destroy()
        print("GTK 4 sidebar, section placement, scroll/draft preservation, narrow navigation and widget controls: passed")


if __name__ == "__main__":
    main()
