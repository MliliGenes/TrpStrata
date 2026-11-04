"""Clock state; its presentation lives in view.json."""
import time

from trp_strata.widget_packages.base import PollingController


class Controller(PollingController):
    def refresh(self, ctx):
        config, now = ctx.props["config"], time.localtime()
        ctx.set_state(
                hours=time.strftime("%H", now),
                minutes=time.strftime("%M", now),
                time=time.strftime(config["clock_format"], now),
                date=time.strftime(config["clock_date_format"], now),
                show_date=bool(config["clock_date_format"]),
                visible=config["clock"],
            )
