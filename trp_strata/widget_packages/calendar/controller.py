"""Calendar data and current-day highlighting."""
import calendar
from datetime import date

from trp_strata.widget_packages.base import PollingController


class Controller(PollingController):
    interval = 30000

    def refresh(self, ctx):
        today = date.today()
        cells = [{"id": i, "text": name, "class": "calendar-weekday"}
                 for i, name in enumerate(("M", "T", "W", "Th", "F", "S", "Su"))]
        for index, day in enumerate(day for week in calendar.monthcalendar(today.year, today.month) for day in week):
            cells.append({"id": index + 7, "text": str(day) if day else "",
                          "class": "calendar-cell today" if day == today.day else "calendar-cell"})
        ctx.set_state(month=today.strftime("%B %Y").upper(), day=str(today.day), cells=cells)
