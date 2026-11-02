"""Background, locally cached website icons; no third-party favicon service."""
from collections import deque
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .storage import CACHE_DIR, write

MAX_BYTES = 1024 * 1024
CACHE_AGE = 7 * 24 * 60 * 60


def site_origin(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Favicons require a website URL")
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    if parsed.port is not None:
        host += f":{parsed.port}"
    return urlunsplit((parsed.scheme, host, "/", "", ""))


class IconLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        rel = (attrs.get("rel") or "").lower().split()
        if tag == "link" and ("icon" in rel or "apple-touch-icon" in rel) and attrs.get("href"):
            self.links.append(attrs["href"])


def download(url):
    if urlsplit(url).scheme not in ("http", "https"):
        raise ValueError("Unsupported icon URL")
    request = Request(url, headers={"User-Agent": "TrpStrata/1.0", "Accept-Encoding": "identity"})
    with urlopen(request, timeout=4) as response:
        data = response.read(MAX_BYTES + 1)
        final_url = response.geturl()
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Website icon response is empty or too large")
    return data, final_url


def png_data(data):
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf, GLib
    loader = GdkPixbuf.PixbufLoader()
    loader.connect("size-prepared", lambda decoder, w, h: decoder.set_size(
        max(1, round(w * min(1, 96 / max(w, h)))), max(1, round(h * min(1, 96 / max(w, h))))))
    try:
        loader.write(data)
        loader.close()
        pixbuf = loader.get_pixbuf()
        if pixbuf is None:
            raise ValueError("Not a usable icon")
        success, encoded = pixbuf.save_to_bufferv("png", [], [])
        if not success:
            raise ValueError("Cannot encode favicon")
        return bytes(encoded)
    except Exception:
        try:
            loader.close()
        except GLib.Error:
            pass
        raise


def load_favicon(origin, cache_dir=None, fetch=download, encode=png_data, cancelled=lambda: False):
    root = Path(cache_dir or os.path.join(CACHE_DIR, "favicons"))
    key = hashlib.sha256(origin.encode()).hexdigest()
    metadata = root / (key + ".json")
    cached = None
    try:
        record = json.loads(metadata.read_text())
        filename = record["file"]
        if isinstance(filename, str) and Path(filename).name == filename and filename.endswith(".png"):
            candidate = root / filename
            if candidate.is_file():
                cached = str(candidate)
                if time.time() - metadata.stat().st_mtime < CACHE_AGE:
                    return cached
    except (OSError, ValueError, KeyError, TypeError):
        pass
    # Discover explicit icons first (including CDN URLs); fall back to /favicon.ico.
    if cancelled():
        return cached
    candidates = []
    try:
        html, final_url = fetch(origin)
        parser = IconLinks()
        parser.feed(html.decode("utf-8", errors="replace"))
        candidates.extend(urljoin(final_url, href) for href in parser.links[:6])
    except Exception:
        pass
    candidates.append(urljoin(origin, "/favicon.ico"))
    for url in dict.fromkeys(candidates):
        if cancelled():
            return cached
        try:
            if urlsplit(url).scheme not in ("http", "https"):
                continue
            data, _final_url = fetch(url)
            encoded = encode(data)
            filename = key + "-" + hashlib.sha256(encoded).hexdigest()[:16] + ".png"
            root.mkdir(parents=True, exist_ok=True)
            destination = root / filename
            # Atomic publication also handles two widget instances fetching one site.
            import tempfile
            with tempfile.NamedTemporaryFile(dir=root, delete=False) as target:
                temporary = target.name
                try:
                    target.write(encoded)
                    target.flush()
                    os.replace(temporary, destination)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            write(str(metadata), json.dumps({"file": filename}) + "\n")
            return str(destination)
        except Exception:
            continue
    return cached


class FaviconModel:
    def __init__(self, fetch=None):
        self.fetch = fetch if fetch is not None else lambda origin: load_favicon(origin, cancelled=lambda: self.closed)
        self.condition = threading.Condition()
        self.entries = {}
        self.queue = deque()
        self.closed = False
        self.thread = None

    def icon(self, url):
        origin = site_origin(url)
        with self.condition:
            path, retry, pending = self.entries.get(origin, (None, 0, False))
            if not self.closed and not pending and time.monotonic() >= retry:
                self.entries[origin] = (path, retry, True)
                self.queue.append(origin)
                if self.thread is None:
                    self.thread = threading.Thread(target=self._run, daemon=True, name="favicons")
                    self.thread.start()
                self.condition.notify_all()
            return path or "web-browser"

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or self.queue)
                if self.closed:
                    return
                origin = self.queue.popleft()
            try:
                path = self.fetch(origin)
            except Exception:
                path = None
            with self.condition:
                if self.closed:
                    return
                self.entries[origin] = (path, time.monotonic() + (CACHE_AGE if path else 300), False)
                self.condition.notify_all()

    def close(self):
        with self.condition:
            self.closed = True
            self.queue.clear()
            self.condition.notify_all()
