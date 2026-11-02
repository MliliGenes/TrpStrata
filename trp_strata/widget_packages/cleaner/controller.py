"""Cache scanning and cleaning handlers."""
from trp_strata.widget_engine import handler
from trp_strata.widget_packages.base import PollingController
from trp_strata.cleaner import CleanerModel


class Controller(PollingController):
    def refresh(self, ctx):
        status, busy = ctx.model("cleaner", CleanerModel).view()
        ctx.set_state(status=status, enabled=not busy)

    @handler
    def scan(self, ctx, event):
        ctx.instance.models["cleaner"].start()
        self.refresh(ctx)

    @handler
    def clean(self, ctx, event):
        ctx.instance.models["cleaner"].start(True)
        self.refresh(ctx)
