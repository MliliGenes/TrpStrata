#!/usr/bin/env python3
"""Rebuild the bundled GTK utility catalogue; not needed when running the app."""
from pathlib import Path
import re
import sys
import textwrap

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trp_strata.widget_styles import CSS, css
from trp_strata.widget_utilities import UTILITIES

START = "/* BEGIN WIDGET UTILITY CATALOGUE */"
END = "/* END WIDGET UTILITY CATALOGUE */"


def selector(name):
    """Compile a finite utility name into native GTK state/descendant selectors."""
    parts = name.split(":")
    escaped = re.sub(r"([^a-zA-Z0-9_-])", r"\\\1", name)
    target, theme = "." + escaped, None
    nodes = {"label": "label", "trough": "trough", "progress": "progress"}
    for variant in parts[:-1]:
        if variant in ("red", "light"):
            theme = variant
        elif variant in ("hover", "active", "focus", "disabled"):
            target += ":" + variant
        else:
            target += " " + nodes[variant]
    if theme:
        return f".desktop-widget.{theme}{target},\n.desktop-widget.{theme} {target}"
    return target


def main():
    # Preserve existing catalogue entries when regenerating, including relative sizes.
    rules = {name: {key: value for key, value in style.items() if key in CSS}
             for name, style in UTILITIES.items()}
    sizes = (0, .15, .2, .25, .35, .45, .5, .55, .72, .74, .76, .78, .8, .82,
             .84, .85, .9, 1, 1.05, 1.1, 1.2, 1.35, 1.5, 1.75, 1.8,
             2, 2.4, 3, 3.25, 3.8, 4, 4.35, 6, 12, 13, 14, 15, 16, 17, 18)
    for size in sizes:
        token, value = f"{size:g}", f"{size:g}em"
        for prefix, prop in (("text", "fontSize"), ("min-w", "minWidth"),
                             ("min-h", "minHeight"), ("rounded", "borderRadius")):
            rules[f"{prefix}-em-{token}"] = {prop: value}
        for axis, edges in (("", ("Top", "Right", "Bottom", "Left")),
                            ("x", ("Left", "Right")), ("y", ("Top", "Bottom")),
                            ("t", ("Top",)), ("r", ("Right",)),
                            ("b", ("Bottom",)), ("l", ("Left",))):
            for prefix, prop in (("p", "padding"), ("m", "margin")):
                rules[f"{prefix}{axis}-em-{token}"] = {prop + edge: value for edge in edges}
    rules.update({
        "text-inherit": {"color": "inherit"},
        "text-theme-primary": {"color": "@ws_ink"},
        "text-theme-muted": {"color": "@ws_muted"},
        "text-theme-accent": {"color": "@ws_accent"},
        "text-theme-level": {"color": "@ws_ink"},
        "tracking-tight": {"letterSpacing": "-0.02em"},
        "tracking-tighter": {"letterSpacing": "-0.035em"},
        "tracking-normal": {"letterSpacing": "0em"},
        "tracking-wide": {"letterSpacing": "0.03em"},
        "tracking-widest": {"letterSpacing": "0.10em"},
        "font-body": {"fontFamily": '"Inter", "DejaVu Sans", sans-serif'},
        "font-display": {"fontFamily": '"Inter", "DejaVu Sans", sans-serif'},
    })
    # These are palette/opacity utilities, not widget-specific control presets.
    for colour, value in (("primary", "@ws_ink"), ("accent", "@ws_accent"), ("on-accent", "@ws_on_accent")):
        for opacity in (5.5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 22, 24, 38, 42, 55, 76):
            for prefix, prop in (("bg", "background"), ("border", "borderColor"), ("text", "color")):
                rules[f"{prefix}-{colour}/{opacity:g}"] = {prop: f"alpha({value}, {opacity / 100:g})"}
    for colour, value in (("accent-soft", "mix(@ws_accent, @ws_on_accent, 0.12)"),
                          ("accent-strong", "mix(@ws_accent, @ws_on_accent, 0.22)"),
                          ("accent-hover", "mix(@ws_accent, @ws_accent_text, 0.2)")):
        for prefix, prop in (("bg", "background"), ("border", "borderColor")):
            rules[f"{prefix}-{colour}"] = {prop: value}
    state_names = (
        "bg-transparent", "bg-accent", "bg-primary/5.5", "bg-primary/6", "bg-primary/9", "bg-primary/10",
        "bg-accent/16", "bg-accent-soft", "bg-accent-strong", "bg-accent-hover", "bg-on-accent/10",
        "border-transparent", "border-accent", "border-primary/8", "border-primary/10", "border-primary/12",
        "border-primary/18", "border-primary/24", "border-accent/38", "border-accent-soft", "border-accent-strong",
        "border-on-accent", "border-on-accent/14", "border-on-accent/22",
        "text-primary", "text-muted", "text-inherit", "text-on-accent", "text-on-accent/55", "text-on-accent/76",
    )
    # State order is stable, as with a precompiled Tailwind stylesheet.
    for state in ("hover", "active", "focus", "disabled"):
        for name in state_names:
            rules[f"{state}:{name}"] = dict(rules[name])
    for theme in ("light", "red"):
        for state in ("", "hover:", "active:", "focus:", "disabled:"):
            for name in state_names:
                rules[f"{theme}:{state}{name}"] = dict(rules[name])
    for name in ("font-medium", "text-em-0.84"):
        rules[f"label:{name}"] = dict(rules[name])
    rules["min-h-em-0.35"] = {"minHeight": "0.35em"}
    for node in ("trough", "progress"):
        for name in ("min-h-em-0.35", "bg-primary/10", "bg-accent", "border-0", "rounded-full", "shadow-none"):
            rules[f"{node}:{name}"] = dict(rules[name])
        for name in ("bg-on-accent", "bg-on-accent/18"):
            rules[f"red:{node}:{name}"] = dict(rules[name])
    lines = [START, "/* Real GTK CSS utilities. CSS order, not class-string order, resolves conflicts.",
             "   Fixed lengths use logical px; -em- classes follow each card's font scale.",
             "   Escaped hover/active/focus/disabled, light/red and label/trough/progress",
             "   prefixes below are real GTK state, theme and subnode selectors.",
             "   gap/grid/grow/alignment/wrapping/size-request classes are native layout",
             "   utilities documented in docs/widget-utilities.md, not browser CSS. */"]
    native = [name for name, style in UTILITIES.items() if any(key not in CSS for key in style)]
    lines.extend(["/* Native GTK layout class reference (implemented by the renderer):",
                  *textwrap.wrap(" ".join(native), width=100, initial_indent="   ", subsequent_indent="   ",
                                 break_long_words=False, break_on_hyphens=False),
                  "*/"])
    for name, style in rules.items():
        if style:
            declarations = css(style).removeprefix("* { ").removesuffix(" }")
            lines.append(f"{selector(name)} {{ {declarations} }}")
    lines.extend([
        "", "/* Theme-aware colours keep red-card contrast without affecting fixed palette utilities. */",
        ".desktop-widget.red.text-theme-primary,",
        ".desktop-widget.red .text-theme-primary { color: @ws_on_accent; }",
        ".desktop-widget.red.text-theme-muted,",
        ".desktop-widget.red.text-theme-accent,",
        ".desktop-widget.red.text-theme-level,",
        ".desktop-widget.red .text-theme-muted,",
        ".desktop-widget.red .text-theme-accent,",
        ".desktop-widget.red .text-theme-level { color: alpha(@ws_on_accent, 0.76); }",
        ".desktop-widget.light.text-theme-level,",
        ".desktop-widget.light .text-theme-level { color: @ws_muted; }",
        END,
    ])
    path = Path(__file__).resolve().parents[1] / "trp_strata/styles/widgets.css"
    source = path.read_text()
    before = source.split(START)[0].rstrip()
    after = source.split(END, 1)[1] if END in source else "\n"
    path.write_text(before + "\n\n" + "\n".join(lines) + after)


if __name__ == "__main__":
    main()
