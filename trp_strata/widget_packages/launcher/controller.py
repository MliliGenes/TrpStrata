"""Application search, pagination and launching."""
from trp_strata.widget_engine import handler
from trp_strata.widget_packages.base import PollingController
from trp_strata.launcher import LauncherModel
from trp_strata.widgets.launcher import app_icon


class Controller(PollingController):
    def refresh(self, ctx):
        model = ctx.model("launcher", LauncherModel)
        page_size = ctx.props.get("page_size", 6)
        entries, pages, _ = model.view(ctx.props.get("apps"), page_size)
        apps = [{"id": app.get_id(), "name": app.get_display_name(), "icon": app_icon(app),
                 "tooltip": app.get_display_name() + ("\n" + app.get_description() if app.get_description() else "")}
                for app in entries]
        ctx.set_state(title=ctx.props.get("title", "App launcher").upper(), query=model.query, apps=apps,
                      empty=[{"id": f"empty-{i}"} for i in range(len(apps), ((page_size + 2) // 3) * 3)],
                      hint="No matching applications." if model.query.strip() else "Search to find installed applications.",
                      show_hint=not entries, can_previous=model.page > 0, can_next=model.page + 1 < pages,
                      page=f"{model.page + 1} / {pages}", show_pages=pages > 1, status=model.status, show_status=bool(model.status))

    @handler
    def search(self, ctx, event):
        ctx.instance.models["launcher"].set_query(event["value"])
        self.refresh(ctx)

    @handler
    def move(self, ctx, event):
        if event.get("args") not in (-1, 1):
            raise ValueError("Page direction must be -1 or 1")
        ctx.instance.models["launcher"].move(event["args"])
        self.refresh(ctx)

    @handler
    def launch(self, ctx, event):
        ctx.instance.models["launcher"].launch(event["args"])
        self.refresh(ctx)
