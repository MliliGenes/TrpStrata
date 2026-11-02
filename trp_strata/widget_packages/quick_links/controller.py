"""Website shortcut state and launch handler."""
from trp_strata.widget_engine import handler
from trp_strata.widget_packages.base import PollingController
from trp_strata.quick_links import DEFAULT_LINKS, QuickLinksModel, normalize_links


class Controller(PollingController):
    def refresh(self, ctx):
        model = ctx.model("quick-links", QuickLinksModel)
        links = normalize_links(ctx.props.get("links", DEFAULT_LINKS))
        ctx.set_state(title=ctx.props.get("title", "Quick links").upper(),
                      links=[{**link, "id": f"link-{index}", "icon": model.icon(link["url"])} for index, link in enumerate(links)],
                      show_hint=not links, status=model.status, show_status=bool(model.status))

    @handler
    def launch(self, ctx, event):
        link = event["args"]
        ctx.instance.models["quick-links"].launch(link["label"], link["url"])
        self.refresh(ctx)
