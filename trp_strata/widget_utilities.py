"""Finite, Tailwind-inspired utilities for native widget styles (no GTK dependency)."""
from difflib import get_close_matches
from pathlib import Path
import re

from .widget_styles import CSS, LAYOUT, LENGTHS, validate


# One spacing unit is four logical pixels, not a browser rem.
SPACING = {str(value): value * 4 for value in (
    0, .5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16,
    20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 72, 80, 96)}
SPACING["px"] = 1


def _registry():
    """Only GTK layout operations live here; appearance comes from widgets.css."""
    result = {}
    for size, pixels in SPACING.items():
        result[f"gap-{size}"] = {"gap": pixels, "rowGap": pixels, "columnGap": pixels}
        result[f"gap-x-{size}"] = {"columnGap": pixels}
        result[f"gap-y-{size}"] = {"rowGap": pixels}
        for prefix, prop in (("w", "width"), ("h", "height")):
            result[f"{prefix}-{size}"] = {prop: pixels}
        result[f"size-{size}"] = {"width": pixels, "height": pixels}
    for name, value in (("left", "start"), ("center", "center"), ("right", "end"),
                        ("start", "start"), ("end", "end")):
        result[f"text-{name}"] = {"textAlign": value}
    for name in ("start", "center", "end", "fill"):
        result[f"self-{name}"] = {"alignSelf": name}
        result[f"vself-{name}"] = {"valignSelf": name}
    for name, prop in (("grow", "expand"), ("vgrow", "vexpand")):
        result[name] = {prop: True}
        result[f"{name}-0"] = {prop: False}
    result.update({
        "text-wrap": {"wrap": True}, "text-nowrap": {"wrap": False},
    })
    for count in range(1, 13):
        result[f"grid-cols-{count}"] = {"columns": ["1fr"] * count}
        result[f"grid-rows-{count}"] = {"rows": ["1fr"] * count}
        result[f"col-span-{count}"] = {"columnSpan": count}
        result[f"row-span-{count}"] = {"rowSpan": count}
        # Tailwind placement is one-based; engine cells are zero-based.
        result[f"col-start-{count}"] = {"column": count - 1}
        result[f"row-start-{count}"] = {"row": count - 1}
    return result


STYLESHEET = Path(__file__).with_name("styles") / "widgets.css"
START = "/* BEGIN WIDGET UTILITY CATALOGUE */"
END = "/* END WIDGET UTILITY CATALOGUE */"


def stylesheet():
    """The real CSS catalogue, also used by standalone renderers."""
    return STYLESHEET.read_text().split(START, 1)[1].split(END, 1)[0]


def _css_registry():
    # Index flat utility declarations, including escaped state/subnode variants.
    # GTK itself parses/applies selectors; this is only a validation/reference index.
    names = {value: key for key, value in CSS.items()}
    result = {}
    source = re.sub(r"/\*.*?\*/", "", stylesheet(), flags=re.DOTALL)
    for selectors, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", source):
        classes = set()
        for selector in selectors.split(","):
            matches = re.findall(r"\.((?:\\.|[\w-])+)", selector)
            if not matches:
                continue
            name = re.sub(r"\\(.)", r"\1", matches[-1])
            # Unprefixed ancestor overrides (e.g. red .text-theme-muted) must not
            # overwrite the base class's metadata.
            if ":" in name or (len(matches) == 1 and selector.strip().startswith(".")):
                classes.add(name)
        style = {}
        for declaration in declarations.split(";"):
            if not declaration.strip():
                continue
            prop, value = (part.strip() for part in declaration.split(":", 1))
            key = names[prop]
            if key in LENGTHS and value.endswith("px"):
                value = float(value[:-2])
            elif key == "fontWeight" and value.isdigit():
                value = int(value)
            style[key] = value
        for name in classes:
            result[name] = validate(style)
    return result


CSS_UTILITIES = _css_registry()
UTILITIES = {**CSS_UTILITIES, **_registry()}


def css_classes(class_name):
    """Strict u: names use the same native CSS class as their unprefixed form."""
    return {token[2:] if token.startswith("u:") else token for token in class_name.split()}


def utility_style(class_name):
    """Validate/index known tokens; u: explicitly requires a known utility.

    Only the layout entries are used to render. Visual entries are catalogue
    metadata: GTK's stylesheet cascade, not this dict, resolves their conflicts.
    Other names remain ordinary CSS classes for backwards compatibility.
    """
    if not isinstance(class_name, str):
        raise TypeError("class_name must be a space-separated string of CSS classes")
    result = {}
    for token in class_name.split():
        strict = token.startswith("u:")
        name = token[2:] if strict else token
        if name not in UTILITIES:
            if strict:
                matches = get_close_matches(name, UTILITIES, n=1)
                hint = f"; did you mean u:{matches[0]}?" if matches else ""
                raise ValueError(f"Unknown widget utility {token!r}{hint}")
            continue
        result.update({key: list(value) if isinstance(value, list) else value
                       for key, value in UTILITIES[name].items()})
    return result


def _expanded(style):
    """Canonicalize shorthands so later utilities/inline styles win on every edge."""
    result = {}
    for key, value in style.items():
        if key in ("padding", "margin"):
            values = list(value) if isinstance(value, (list, tuple)) else [value]
            top = values[0]
            right = values[1] if len(values) > 1 else top
            bottom = values[2] if len(values) > 2 else top
            left = values[3] if len(values) > 3 else right
            result.update({key + edge: pixels for edge, pixels in zip(
                ("Top", "Right", "Bottom", "Left"), (top, right, bottom, left))})
        elif key == "gap":
            result.update(gap=value, rowGap=value, columnGap=value)
        else:
            result[key] = value
    return result


def resolve_style(class_name, style=None):
    """Resolve GTK layout only; visual utilities are applied by the CSS stylesheet."""
    explicit = validate(style)
    utilities = {key: value for key, value in utility_style(class_name).items() if key in LAYOUT}
    if not utilities:
        return explicit
    return validate({**utilities, **_expanded(explicit)})
