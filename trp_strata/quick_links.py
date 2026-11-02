"""Web shortcuts shared by the desktop widget and its editor."""
from urllib.parse import urlsplit

DEFAULT_LINKS = (
    {"label": "42 Intra", "url": "https://intra.42.fr"},
    {"label": "GitHub", "url": "https://github.com"},
)


def normalize_links(links):
    if not isinstance(links, (list, tuple)):
        raise ValueError("Links must be a list of labels and URLs")
    result = []
    for index, link in enumerate(links, 1):
        if not isinstance(link, dict):
            raise ValueError(f"Link {index} needs a label and URL")
        label, url = link.get("label", ""), link.get("url", "")
        if not isinstance(label, str) or not isinstance(url, str) or not label.strip() or not url.strip():
            raise ValueError(f"Link {index} needs a label and URL")
        url = url.strip()
        try:
            if not urlsplit(url).scheme:
                url = "https://" + url
            parsed = urlsplit(url)
            valid = parsed.scheme in ("http", "https") and parsed.hostname and not any(c.isspace() for c in url)
            parsed.port  # Validate malformed/out-of-range port numbers too.
        except ValueError:
            valid = False
        if not valid:
            raise ValueError(f"Link {index}: enter a valid http:// or https:// website address")
        result.append({"label": label.strip(), "url": url})
    return result


def open_url(url):
    from gi.repository import Gdk, Gio, Gtk
    display = Gdk.Display.get_default()
    context = display.get_app_launch_context() if display else Gio.AppLaunchContext()
    if display:
        context.set_timestamp(Gtk.get_current_event_time())
    if not Gio.AppInfo.launch_default_for_uri(url, context):
        raise RuntimeError("No browser could open this link")


class QuickLinksModel:
    def __init__(self, opener=open_url, favicons=None):
        from .favicons import FaviconModel
        self.favicons = favicons if favicons is not None else FaviconModel()
        self.opener = opener
        self.status = ""

    def icon(self, url):
        return self.favicons.icon(url)

    def close(self):
        self.favicons.close()

    def launch(self, label, url):
        try:
            link = normalize_links([{"label": label, "url": url}])[0]
            self.opener(link["url"])
            self.status = ""
        except Exception as error:
            self.status = f"Could not open {label}: {error}"
