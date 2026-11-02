"""Shared lifecycle for controllers backed by polling models."""
from trp_strata.widget_engine import Controller


class PollingController(Controller):
    interval = 1000

    def mount(self, ctx):
        self.refresh(ctx)
        ctx.every(self.interval, lambda: self.refresh(ctx))

    def props_changed(self, ctx, previous):
        self.refresh(ctx)
