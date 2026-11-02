"""Notes update only when their props change."""
from trp_strata.widget_engine import Controller as BaseController
from trp_strata.widgets.notes import DEFAULT_TITLE, DEFAULT_TEXT


class Controller(BaseController):
    def mount(self, ctx):
        self.props_changed(ctx, {})

    def props_changed(self, ctx, previous):
        ctx.set_state(title=ctx.props.get("title", DEFAULT_TITLE).upper(),
                      text=ctx.props.get("text", DEFAULT_TEXT))
