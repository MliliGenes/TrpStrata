"""Bounded, background filename indexing and fuzzy matching; no GTK dependency."""
from difflib import SequenceMatcher
import heapq
import os
from pathlib import Path
import threading
import unicodedata


SKIP_DIRS = {"node_modules", "__pycache__", "venv", "env", "target", "build", "dist", "cache"}


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def fuzzy_score(query, name):
    """Prefer exact/substring names, then abbreviations and small spelling errors."""
    if query == name:
        return 1000
    if name.startswith(query):
        return 900 - min(len(name) - len(query), 100)
    if query in name:
        return 750 - min(name.index(query), 100)
    positions, start = [], 0
    for char in query:
        index = name.find(char, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    else:
        return 500 - min(positions[-1] - positions[0] - len(query), 150) if positions else 0
    if len(query) >= 4:
        # Compare words as well as the full stem, keeping typos useful for long names.
        words = name.replace("_", " ").replace("-", " ").replace(".", " ").split()
        similarity = max((SequenceMatcher(None, query, word).ratio() for word in [name, *words]), default=0)
        if similarity >= .72:
            return round(300 * similarity)
    return 0


def scan_files(root, cancelled=lambda: False, limit=50000):
    """Do not follow directory symlinks or descend into hidden/generated trees."""
    entries, pending, seen = [], [root], 0
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as children:
                for child in children:
                    if cancelled():
                        return (), False
                    seen += 1
                    if seen > limit * 4:
                        return tuple(entries), True
                    if child.name.startswith("."):
                        continue
                    try:
                        if child.is_dir(follow_symlinks=False):
                            if child.name not in SKIP_DIRS:
                                pending.append(child.path)
                        elif child.is_file(follow_symlinks=False):
                            relative = os.path.relpath(child.path, root)
                            entries.append((child.path, normalize(child.name), normalize(relative)))
                            if len(entries) >= limit:
                                return tuple(entries), True
                    except OSError:
                        continue
        except OSError:
            if directory == root:
                raise
    return tuple(entries), False


def search_files(index, query, cancelled=lambda: False, limit=6):
    words = normalize(query).split()
    if not words:
        return ()
    def matches():
        for path, name, relative in index:
            if cancelled():
                return
            scores = [max(fuzzy_score(word, name), 100 if word in relative else 0) for word in words]
            if all(scores):
                yield (-sum(scores), len(name), path)
    return tuple(item[2] for item in heapq.nsmallest(limit, matches()))


def open_file(path):
    from gi.repository import Gio, Gdk, Gtk
    if not os.path.isfile(path):
        raise FileNotFoundError("File no longer exists. Refresh the search index.")
    display = Gdk.Display.get_default()
    context = display.get_app_launch_context() if display else Gio.AppLaunchContext()
    if display:
        context.set_timestamp(Gtk.get_current_event_time())
    if not Gio.AppInfo.launch_default_for_uri(Path(path).as_uri(), context):
        raise RuntimeError("No application could open this file.")


def file_icon(path):
    from gi.repository import Gio
    content_type, _uncertain = Gio.content_type_guess(path, None)
    return Gio.content_type_get_icon(content_type or "application/octet-stream").to_string() or "text-x-generic"


class FileSearchModel:
    def __init__(self, root="~", scanner=scan_files, opener=open_file):
        self.condition = threading.Condition()
        self.closed = threading.Event()
        self.scanner, self.opener = scanner, opener
        self.root = os.path.abspath(os.path.expanduser(root))
        self.query, self.status = "", "Indexing files…"
        self.results, self.busy = (), True
        self.version, self.revision = 0, 0
        self.thread = threading.Thread(target=self._run, name="file-search", daemon=True)
        self.thread.start()

    def configure(self, root):
        root = os.path.abspath(os.path.expanduser(root))
        with self.condition:
            if root != self.root:
                self.root = root
                self.refresh()

    def refresh(self):
        with self.condition:
            self.version += 1
            self.revision += 1
            self.results, self.busy, self.status = (), True, "Indexing files…"
            self.condition.notify_all()

    def set_query(self, text):
        with self.condition:
            self.query = text
            self.revision += 1
            self.results, self.busy = (), True
            self.status = "Searching…" if text.strip() else ""
            self.condition.notify_all()

    def view(self):
        with self.condition:
            return self.results, self.status, self.busy

    def launch(self, path):
        try:
            self.opener(path)
        except Exception as error:
            with self.condition:
                self.status = str(error)

    def _run(self):
        built, processed, index, capped = -1, -1, (), False
        while not self.closed.is_set():
            with self.condition:
                self.condition.wait_for(lambda: self.closed.is_set() or processed != self.revision)
                if self.closed.is_set():
                    return
                version, revision, root, query = self.version, self.revision, self.root, self.query
            try:
                if built != version:
                    index, capped = self.scanner(root, lambda: self.closed.is_set() or version != self.version)
                    if self.closed.is_set() or version != self.version:
                        continue
                    built = version
                results = search_files(index, query, lambda: self.closed.is_set() or revision != self.revision)
                status = (f"{len(index):,} files indexed" + (" · limit reached; choose a smaller folder" if capped else ""))
                if query.strip() and not results:
                    status = "No matching files. " + status
            except OSError as error:
                results, status = (), f"Cannot search this folder: {error}"
            with self.condition:
                if revision == self.revision:
                    self.results, self.status, self.busy = results, status, False
                    processed = revision
                    self.condition.notify_all()

    def close(self):
        self.closed.set()
        with self.condition:
            self.condition.notify_all()
