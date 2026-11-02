"""Sample independent CPU, memory and filesystem metrics."""
from trp_strata.widget_packages.base import PollingController
from trp_strata.widgets.system import SystemStats


class Controller(PollingController):
    def refresh(self, ctx):
        values = ctx.model("system", SystemStats).sample()
        ctx.set_state(metrics=[{"id": name, "value": value or 0, "available": value is not None,
                                "text": f"{value:.0%}" if value is not None else "Measuring…"}
                               for name, value in values.items()])
