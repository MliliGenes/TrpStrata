"""Logtime state and month-navigation actions."""
from trp_strata.widget_engine import handler
from trp_strata.widget_packages.base import PollingController
from trp_strata.logtime import LogtimeModel
from trp_strata.settings import validate


class Controller(PollingController):
    def refresh(self, ctx):
        config = ctx.props["config"]
        username = validate("logtime_username", ctx.props.get("username") if ctx.props.get("username") is not None else config["logtime_username"])
        goal = validate("logtime_goal", ctx.props.get("goal") if ctx.props.get("goal") is not None else config["logtime_goal"])
        data = ctx.model("logtime", LogtimeModel).view(username)
        hours = data["hours"]
        fraction = min(1, hours / goal) if hours is not None else 0
        status = ("Set logtime_username in settings" if not username else data["error"] or
                  ("Updating…" if data["loading"] and hours is not None else "Loading…" if data["loading"] else f"Goal · {goal:g} hours"))
        ctx.set_state(login=username.upper() if username else "LOGTIME", fraction=fraction,
                      percent=f"{fraction:.0%}" if hours is not None else "—", hours=f"{hours:g}" if hours is not None else "—",
                      month=data["start"].strftime("%B %Y"), period=f'{data["start"]:%b %d, %Y} – {data["end"]:%b %d, %Y}',
                      refresh_label="Updating…" if data["loading"] else "Refresh",
                      can_refresh=bool(username) and not data["loading"], status=status)

    @handler
    def shift(self, ctx, event):
        if event.get("args") not in (-1, 1):
            raise ValueError("Month direction must be -1 or 1")
        ctx.instance.models["logtime"].shift(event["args"])
        self.refresh(ctx)

    @handler
    def reload(self, ctx, event):
        ctx.instance.models["logtime"].refresh()
        self.refresh(ctx)
