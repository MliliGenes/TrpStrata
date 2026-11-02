"""Search local filenames without blocking the desktop UI."""
import os

from ..components import Button, Column, Row, Search, Text, component, use_model
from ..file_search import FileSearchModel, file_icon


@component
def FileSearch(config, title="File search", root="~"):
    if not isinstance(root, str) or not root.strip():
        raise ValueError("File Search root must be a folder path")
    model = use_model(lambda: FileSearchModel(root), key="file-search")
    model.configure(root)
    results, status, busy = model.view()
    return Column(
        Row(Text(title.upper(), class_name="widget-label", align="start", expand=True),
            Button("Refresh", on_click=model.refresh, sensitive=not busy), spacing=8),
        Search(model.query, on_change=model.set_query, placeholder="Find files by name…", key="file-query"),
        Column([
            Column(Button(os.path.basename(path), system_icon=file_icon(path),
                          on_click=lambda path=path: model.launch(path), tooltip=path),
                   Text(os.path.relpath(os.path.dirname(path), model.root), align="start",
                        wrap=True, max_width_chars=36, class_name="file-search-path"),
                   spacing=3, key=path)
            for path in results
        ], spacing=8),
        Text("Type a name, abbreviation or a few words from the path.",
             visible=not model.query.strip(), wrap=True, max_width_chars=36, align="start"),
        Text(status, wrap=True, max_width_chars=36, align="start", class_name="file-search-path"),
        spacing=10, class_name="launcher-card file-search-card",
    )
