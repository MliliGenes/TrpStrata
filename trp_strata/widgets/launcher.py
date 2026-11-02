"""One-click desktop application launcher, with optional pinned desktop IDs."""
from ..components import Button, Column, Row, Search, Text, component, use_model
from ..launcher import LauncherModel


def app_icon(app):
    icon = app.get_icon()
    return (icon.to_string() if icon is not None else None) or "application-x-executable"


@component
def Launcher(config, title="App launcher", apps=None, page_size=6):
    model = use_model(LauncherModel, key="launcher")
    entries, pages, _all_apps = model.view(apps, page_size)
    cells = [
        Button(app.get_display_name(), key=app.get_id(),
               tooltip=app.get_display_name() + ("\n" + app.get_description() if app.get_description() else ""),
               system_icon=app_icon(app), icon_position="top", expand=True,
               on_click=lambda app_id=app.get_id(): model.launch(app_id),
               class_name="launcher-app")
        for app in entries
    ]
    # Keep the same three-column footprint on short pages and filtered results.
    cells.extend(Column(class_name="launcher-empty", expand=True, key=f"empty-{index}")
                 for index in range(len(cells), ((page_size + 2) // 3) * 3))
    return Column(
        Text(title.upper(), class_name="widget-label", align="start"),
        Search(model.query, on_change=model.set_query, placeholder="Search installed apps…", key="app-search"),
        Column([Row(cells[index:index + 3], homogeneous=True, spacing=8, key=f"row-{index // 3}")
                for index in range(0, len(cells), 3)], spacing=8, homogeneous=True),
        Text("No matching applications." if model.query.strip() else "Search to find installed applications.",
             visible=not entries, wrap=True, max_width_chars=30, align="start"),
        Row(Button("Previous", on_click=lambda: model.move(-1), sensitive=model.page > 0),
            Text(f"{model.page + 1} / {pages}", expand=True),
            Button("Next", on_click=lambda: model.move(1), sensitive=model.page + 1 < pages),
            visible=pages > 1, spacing=8),
        Text(model.status, visible=bool(model.status), wrap=True, max_width_chars=30, align="start"),
        spacing=10, class_name="launcher-card",
    )
