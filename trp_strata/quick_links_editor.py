"""GTK 4 editor for one Quick Links desktop card."""
from gi.repository import Adw, GLib, Gtk

from . import layout
from .quick_links import DEFAULT_LINKS, normalize_links


def show_editor(parent, widget_id):
    try:
        placement = next((item for item in layout.load_layout()
                          if item.id == widget_id and item.component == "QuickLinks"), None)
        if placement is None:
            raise ValueError("This Quick Links widget is no longer in the layout")
        links = normalize_links(placement.props.get("links", DEFAULT_LINKS))
    except (OSError, ValueError) as error:
        parent.toasts.add_toast(Adw.Toast(title=str(error)))
        return None
    dialog = Gtk.Dialog(title="Edit quick links", transient_for=parent, modal=True,
                        default_width=520, default_height=460)
    dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
    dialog.add_button("Save", Gtk.ResponseType.ACCEPT).add_css_class("suggested-action")
    content = dialog.get_content_area()
    content.set_spacing(12)
    for edge in ("top", "bottom", "start", "end"):
        getattr(content, f"set_margin_{edge}")(16)
    content.append(Gtk.Label(label="Widget title", xalign=0))
    dialog.title_entry = Gtk.Entry(text=str(placement.props.get("title", "Quick links")))
    content.append(dialog.title_entry)
    content.append(Gtk.Label(label="Give each website a name and an address.", xalign=0))
    rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=200)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_child(rows)
    content.append(scroll)
    dialog.link_entries = []

    def add_link(label="", url=""):
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header = Gtk.Box(spacing=8)
        name = Gtk.Entry(text=label, placeholder_text="Link name", hexpand=True)
        address = Gtk.Entry(text=url, placeholder_text="https://example.com", hexpand=True)
        remove = Gtk.Button(label="Remove")
        record = (row, name, address)
        def remove_link(_button):
            dialog.link_entries.remove(record)
            rows.remove(row)
        remove.connect("clicked", remove_link)
        header.append(name)
        header.append(remove)
        row.append(header)
        row.append(address)
        rows.append(row)
        dialog.link_entries.append(record)
        return name

    dialog.add_link = add_link
    for link in links:
        add_link(link["label"], link["url"])
    add = Gtk.Button(label="Add link", halign=Gtk.Align.START)
    add.connect("clicked", lambda *_: add_link().grab_focus())
    content.append(add)
    error_label = Gtk.Label(wrap=True, xalign=0, visible=False, css_classes=["error"])
    content.append(error_label)

    def show_error(error):
        error_label.set_text(str(error))
        error_label.set_visible(True)

    def busy(value):
        content.set_sensitive(not value)
        dialog.set_deletable(not value)
        for response in (Gtk.ResponseType.ACCEPT, Gtk.ResponseType.CANCEL):
            dialog.set_response_sensitive(response, not value)

    def respond(_dialog, response):
        if response != Gtk.ResponseType.ACCEPT:
            dialog.destroy()
            return
        try:
            updated = normalize_links([{"label": name.get_text(), "url": address.get_text()}
                                       for _row, name, address in dialog.link_entries])
        except ValueError as error:
            show_error(error)
            return
        title = dialog.title_entry.get_text()
        busy(True)
        def finish(future):
            try:
                future.result()
            except Exception as error:
                busy(False)
                show_error(error)
            else:
                dialog.destroy()
                parent.load_widget_rows()
                parent.toasts.add_toast(Adw.Toast(title="Quick links saved"))
            return False
        parent.widget_pool.submit(layout.save_quick_links, widget_id, title, updated).add_done_callback(
            lambda future: GLib.idle_add(finish, future))

    dialog.connect("response", respond)
    dialog.present()
    return dialog
