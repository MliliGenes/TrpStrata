"""Validated structured styles shared by Python and JSON views (no GTK dependency)."""
import math
import re

CSS = {
    "background": "background", "color": "color", "fontFamily": "font-family",
    "fontSize": "font-size", "fontWeight": "font-weight", "fontStyle": "font-style",
    "border": "border", "borderRadius": "border-radius", "borderColor": "border-color",
    "borderWidth": "border-width", "borderStyle": "border-style", "boxShadow": "box-shadow",
    "padding": "padding", "paddingTop": "padding-top", "paddingRight": "padding-right",
    "paddingBottom": "padding-bottom", "paddingLeft": "padding-left",
    "margin": "margin", "marginTop": "margin-top", "marginRight": "margin-right",
    "marginBottom": "margin-bottom", "marginLeft": "margin-left",
    "minWidth": "min-width", "minHeight": "min-height", "letterSpacing": "letter-spacing",
}
LENGTHS = {key for key in CSS if key.startswith(("padding", "margin", "min"))} | {
    "fontSize", "borderRadius", "borderWidth", "letterSpacing"}
EM_LENGTH = re.compile(r"-?(?:\d+(?:\.\d+)?)em\Z")
LAYOUT = {"width", "height", "gap", "rowGap", "columnGap", "alignSelf", "valignSelf",
          "expand", "vexpand", "textAlign", "wrap", "columns", "rows", "column", "row",
          "columnSpan", "rowSpan"}


def tracks(value):
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("Grid tracks must be a nonempty list of pixel sizes, 'auto', or fractions like '1fr'")
    for track in value:
        if type(track) in (int, float) and math.isfinite(track) and track >= 0:
            continue
        if track == "auto":
            continue
        if isinstance(track, str) and track.endswith("fr"):
            try:
                weight = float(track[:-2])
                if math.isfinite(weight) and weight > 0:
                    continue
            except ValueError:
                pass
        raise ValueError(f"Invalid grid track: {track!r}")
    return tuple(value)


def validate(style):
    if style is None:
        return {}
    if not isinstance(style, dict):
        raise TypeError("style must be an object")
    for key, value in style.items():
        if key not in CSS and key not in LAYOUT:
            raise ValueError(f"Unsupported style property: {key}")
        if key in ("columns", "rows"):
            tracks(value)
        elif key in ("alignSelf", "valignSelf", "textAlign"):
            if value not in ("start", "center", "end", "fill"):
                raise ValueError(f"{key} must be start, center, end or fill")
        elif key in ("expand", "vexpand", "wrap"):
            if type(value) is not bool:
                raise ValueError(f"{key} must be boolean")
        elif key in ("column", "row", "columnSpan", "rowSpan"):
            if type(value) is not int or value < (1 if key.endswith("Span") else 0):
                raise ValueError(f"Invalid {key}: {value!r}")
        elif key in LENGTHS or key in ("width", "height", "gap", "rowGap", "columnGap"):
            values = value if key in ("padding", "margin") and isinstance(value, (list, tuple)) else [value]
            def valid_length(v):
                negative_allowed = key == "letterSpacing"
                if key in LENGTHS and isinstance(v, str) and EM_LENGTH.fullmatch(v):
                    number = float(v[:-2])
                    return math.isfinite(number) and (negative_allowed or number >= 0)
                return type(v) in (int, float) and math.isfinite(v) and (negative_allowed or v >= 0)
            if not 1 <= len(values) <= 4 or any(not valid_length(v) for v in values):
                raise ValueError(f"{key} needs finite pixel values or CSS em lengths (nonnegative except letterSpacing)")
        elif key == "fontWeight":
            if value not in ("normal", "bold") and (type(value) is not int or not 100 <= value <= 1000):
                raise ValueError("Invalid fontWeight")
        elif not isinstance(value, str) or not value.strip() or any(c in value for c in "{};\n\r"):
            raise ValueError(f"Invalid CSS value for {key}")
    return dict(style)


def css(style):
    declarations = []
    for key, value in style.items():
        if key not in CSS:
            continue
        if key in LENGTHS:
            values = value if isinstance(value, (list, tuple)) else [value]
            value = " ".join(v if isinstance(v, str) else f"{v:g}px" for v in values)
        declarations.append(f"{CSS[key]}: {value};")
    return "* { " + " ".join(declarations) + " }"


def grid_positions(children, columns):
    """Row-major placement with explicit zero-based cells and collision detection."""
    occupied, result = set(), []
    for child in children:
        style = child.props.get("style", {})
        width, height = style.get("columnSpan", 1), style.get("rowSpan", 1)
        if width > columns:
            raise ValueError("columnSpan exceeds grid column count")
        row, column = style.get("row"), style.get("column")
        if column is not None and column + width > columns:
            raise ValueError("Grid child extends beyond declared columns")
        last_row = max((y for x, y in occupied), default=-1) + 1
        candidates = ((r, c) for r in ([row] if row is not None else range(last_row + 1))
                      for c in ([column] if column is not None else range(columns - width + 1)))
        for r, c in candidates:
            cells = {(x, y) for x in range(c, c + width) for y in range(r, r + height)}
            if not cells & occupied:
                occupied.update(cells)
                result.append((c, r, width, height))
                break
        else:
            raise ValueError("Grid cells overlap or cannot be placed")
    return result


def track_sizes(specs, requirements, gap, available=None):
    """Resolve content minima and distribute remaining space to fractional tracks."""
    sizes = [float(track) if type(track) in (int, float) else 0.0 for track in specs]
    for start, span, minimum in sorted(requirements, key=lambda item: item[1]):
        missing = minimum - sum(sizes[start:start + span]) - gap * (span - 1)
        if missing > 0:
            flexible = [i for i in range(start, start + span) if isinstance(specs[i], str)]
            for i in flexible or list(range(start, start + span)):
                sizes[i] += missing / len(flexible or list(range(start, start + span)))
    weights = {i: float(track[:-2]) for i, track in enumerate(specs)
               if isinstance(track, str) and track.endswith("fr")}
    if available is not None and weights:
        budget = available - gap * (len(specs) - 1) - sum(v for i, v in enumerate(sizes) if i not in weights)
        active = dict(weights)
        while active:
            unit = budget / sum(active.values())
            constrained = [i for i, weight in active.items() if sizes[i] > unit * weight]
            if not constrained:
                for i, weight in active.items():
                    sizes[i] = max(sizes[i], unit * weight)
                break
            for i in constrained:
                budget -= sizes[i]
                del active[i]
    # Cumulative rounding keeps adjacent edges consistent.
    edges, total = [0], 0.0
    for size in sizes:
        total += size
        edges.append(round(total))
    return [edges[i + 1] - edges[i] for i in range(len(sizes))]
