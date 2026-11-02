"""Filename search, refresh and open handlers."""
import os

from trp_strata.widget_engine import handler
from trp_strata.widget_packages.base import PollingController
from trp_strata.file_search import FileSearchModel, file_icon


class Controller(PollingController):
    def refresh(self, ctx):
        root = ctx.props.get("root", "~")
        if not isinstance(root, str) or not root.strip():
            raise ValueError("File Search root must be a folder path")
        model = ctx.model("file-search", lambda: FileSearchModel(root))
        model.configure(root)
        results, status, busy = model.view()
        ctx.set_state(title=ctx.props.get("title", "File search").upper(), query=model.query,
                      can_refresh=not busy, show_hint=not model.query.strip(), status=status,
                      results=[{"id": path, "name": os.path.basename(path), "icon": file_icon(path),
                                "directory": os.path.relpath(os.path.dirname(path), model.root)} for path in results])

    @handler
    def search(self, ctx, event):
        ctx.instance.models["file-search"].set_query(event["value"])
        self.refresh(ctx)

    @handler
    def reload(self, ctx, event):
        ctx.instance.models["file-search"].refresh()
        self.refresh(ctx)

    @handler
    def launch(self, ctx, event):
        ctx.instance.models["file-search"].launch(event["args"])
        self.refresh(ctx)
