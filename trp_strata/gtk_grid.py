"""GTK grid with content-aware pixel, auto and weighted fractional tracks."""
from gi.repository import Gtk, Gdk

from .widget_styles import track_sizes


class Grid(Gtk.Grid):
    def __init__(self):
        super().__init__()
        self.columns = ("1fr",)
        self.rows = ("auto",)
        self.cells = []
        self.column_gap = self.row_gap = 0

    def configure(self, columns, rows, cells, column_gap, row_gap):
        self.columns, self.rows, self.cells = columns, rows, cells
        self.column_gap, self.row_gap = column_gap, row_gap
        self.queue_resize()

    def insets(self):
        context = self.get_style_context()
        state = self.get_state_flags()
        padding, border = context.get_padding(state), context.get_border(state)
        return (padding.left + border.left, padding.top + border.top,
                padding.right + border.right, padding.bottom + border.bottom)

    def sizes(self, width=None, height=None, natural=False):
        cells = [(widget, c, r, w, h) for widget, c, r, w, h in self.cells if widget.get_visible()]
        row_count = max([len(self.rows)] + [r + h for _, c, r, w, h in cells])
        rows = tuple(self.rows) + ("auto",) * (row_count - len(self.rows))
        index = 1 if natural else 0
        columns = track_sizes(self.columns,
                              [(c, w, widget.get_preferred_width()[index]) for widget, c, r, w, h in cells],
                              self.column_gap, width)
        row_sizes = track_sizes(rows, [(r, h, widget.get_preferred_height_for_width(
            max(1, sum(columns[c:c + w]) + self.column_gap * (w - 1)))[index])
            for widget, c, r, w, h in cells], self.row_gap, height)
        return columns, row_sizes

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_get_preferred_width(self):
        left, _, right, _ = self.insets()
        minimum = self.get_style_context().get_property("min-width", self.get_state_flags())
        return tuple(max(minimum, sum(self.sizes(natural=natural)[0]) + self.column_gap * (len(self.columns) - 1))
                     + left + right for natural in (False, True))

    def do_get_preferred_height(self):
        return self.do_get_preferred_height_for_width(self.do_get_preferred_width()[1])

    def do_get_preferred_height_for_width(self, width):
        left, top, right, bottom = self.insets()
        result = []
        minimum = self.get_style_context().get_property("min-height", self.get_state_flags())
        for natural in (False, True):
            rows = self.sizes(max(0, width - left - right), natural=natural)[1]
            result.append(max(minimum, sum(rows) + self.row_gap * (len(rows) - 1)) + top + bottom)
        return tuple(result)

    def do_size_allocate(self, allocation):
        # Initialize GTK's CSS gadget before applying our track allocation.
        Gtk.Grid.do_size_allocate(self, allocation)
        left, top, right, bottom = self.insets()
        columns, rows = self.sizes(max(0, allocation.width - left - right),
                                   max(0, allocation.height - top - bottom))
        for widget, c, r, w, h in self.cells:
            if not widget.get_visible():
                continue
            rect = Gdk.Rectangle()
            rect.x = allocation.x + left + sum(columns[:c]) + self.column_gap * c
            rect.y = allocation.y + top + sum(rows[:r]) + self.row_gap * r
            rect.width = max(1, sum(columns[c:c + w]) + self.column_gap * (w - 1))
            rect.height = max(1, sum(rows[r:r + h]) + self.row_gap * (h - 1))
            widget.size_allocate(rect)
