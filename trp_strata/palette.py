"""Colours from a picture: one accent and a family of tinted neutrals, in a light and a dark set.

Colours are grouped perceptually in OKLab. Meaningful accent colours stand out from
the dominant cast; tiny specks and transparent pixels do not drive the theme.
"""
import colorsys

EXTRACTION_VERSION = 2


# --- colour maths -----------------------------------------------------------------

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02X}" for c in rgb)


def hsl(h, s, l):
    """Hue in degrees, saturation and lightness in 0..1."""
    return rgb_to_hex(colorsys.hls_to_rgb((h % 360) / 360, l, s))


def luminance(hexcolor):
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in hex_to_rgb(hexcolor))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def reach_contrast(h, s, l, against, target, step):
    """Walk lightness (step < 0 darkens) until the colour reads against the background."""
    for _ in range(100):
        c = hsl(h, s, l)
        if contrast(c, against) >= target or not 0.02 < l < 0.98:
            return c
        l += step
    return hsl(h, s, l)


def rgba(hexcolor, alpha):
    r, g, b = (round(c * 255) for c in hex_to_rgb(hexcolor))
    return f"rgba({r}, {g}, {b}, {alpha})"


# --- extraction -------------------------------------------------------------------

def image_colors(path, size=120):
    """The picture as (hue°, saturation, lightness) samples, read at a small size."""
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, size, size, True)
    data, stride, n = pb.get_pixels(), pb.get_rowstride(), pb.get_n_channels()
    has_alpha = pb.get_has_alpha()
    samples = []
    for y in range(pb.get_height()):
        row = y * stride
        for x in range(pb.get_width()):
            i = row + x * n
            if has_alpha and data[i + 3] < 128:
                continue
            h, l, s = colorsys.rgb_to_hls(data[i] / 255, data[i + 1] / 255, data[i + 2] / 255)
            samples.append((h * 360, s, l))
    return samples


def hue_distance(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def from_image(path):
    """The light and dark palettes for a picture."""
    return build(image_colors(path))


def build(samples):
    from .color_extraction import select
    dom_h, dom_s, acc_h, acc_s, mono = select(samples)

    # neutrals take a visible tint of the cast (none for black-and-white pictures)
    if mono or dom_s < 0.06:
        tint_h, tint_s = dom_h, 0.0
    else:
        tint_h, tint_s = dom_h, min(dom_s, 0.45) * 0.85

    def ansi(lightness, bright, sat):
        red_h, red_s = (6, sat) if mono else (acc_h, acc_s)
        hues = {1: red_h, 2: 105, 3: 40, 4: 212, 5: 320, 6: 178}
        base = [hsl(hues[i], sat if i != 1 else red_s, lightness) for i in range(1, 7)]
        hi = [hsl(hues[i], sat if i != 1 else red_s, bright) for i in range(1, 7)]
        return base, hi

    l_paper = hsl(tint_h, tint_s, 0.92)
    l_ink = hsl(tint_h, min(tint_s, 0.18), 0.11)
    if mono:                                          # graphite on paper, silver at night
        l_accent, l_accent_text = hsl(tint_h, 0, 0.24), hsl(tint_h, 0, 0.20)
    else:
        l_accent = reach_contrast(acc_h, acc_s, 0.50, l_paper, 3.2, -0.02)
        l_accent_text = reach_contrast(acc_h, acc_s, 0.42, l_paper, 4.6, -0.02)
    l_on = "#FFFFFF" if contrast("#FFFFFF", l_accent) >= contrast("#000000", l_accent) else "#000000"
    l_base, l_hi = ansi(0.38, 0.46, 0.55)
    l_muted = reach_contrast(tint_h, tint_s * 0.6, 0.42, l_paper, 4.5, -0.01)

    d_paper = hsl(tint_h, tint_s * 0.9, 0.10)
    d_ink = hsl(tint_h, tint_s * 0.5, 0.90)
    if mono:
        d_accent, d_accent_text = hsl(tint_h, 0, 0.80), hsl(tint_h, 0, 0.86)
    else:
        d_accent = reach_contrast(acc_h, acc_s, 0.58, d_paper, 4.6, 0.02)
        d_accent_text = reach_contrast(acc_h, acc_s, 0.66, d_paper, 6.0, 0.02)
    d_on = d_paper if contrast(d_paper, d_accent) >= 4.5 else "#FFFFFF"
    d_base, d_hi = ansi(0.66, 0.76, 0.48)
    d_muted = reach_contrast(tint_h, tint_s * 0.5, 0.60, hsl(tint_h, tint_s * 0.9, 0.14), 4.5, 0.01)

    return {
        "light": {
            "paper": l_paper, "paper2": hsl(tint_h, tint_s, 0.86), "sheet": hsl(tint_h, tint_s, 0.965),
            "ink": l_ink, "muted": l_muted,
            "accent": l_accent, "accent_text": l_accent_text, "on_accent": l_on,
            "ansi": [l_ink, *l_base, l_muted, hsl(tint_h, tint_s * 0.6, 0.30), *l_hi,
                     hsl(tint_h, tint_s, 0.20)],
        },
        "dark": {
            "paper": d_paper, "paper2": hsl(tint_h, tint_s * 0.9, 0.075),
            "sheet": hsl(tint_h, tint_s * 0.9, 0.14), "ink": d_ink, "muted": d_muted,
            "accent": d_accent, "accent_text": d_accent_text, "on_accent": d_on,
            "ansi": [hsl(tint_h, tint_s * 0.9, 0.18), *d_base, hsl(tint_h, tint_s * 0.5, 0.80),
                     hsl(tint_h, tint_s * 0.5, 0.38), *d_hi, hsl(tint_h, tint_s * 0.3, 0.97)],
        },
    }


# --- GTK stylesheet ---------------------------------------------------------------

GLASS = """
/* transparent windows: the wallpaper shows through, text stays solid. Anything that holds
   text adds a second translucent layer, so reading areas stay ~84% solid. */
window.background:not(.popup):not(tooltip):not(.solid-csd):not(.desktopwindow) {
  background-color: alpha(@window_bg_color, 0.70);
}
headerbar, .titlebar:not(headerbar) { background-color: alpha(@headerbar_bg_color, 0.45); }
headerbar:backdrop, .titlebar:not(headerbar):backdrop { background-color: alpha(@headerbar_backdrop_color, 0.4); }
.view, textview text, iconview, treeview.view, list, listview, columnview, .content-view,
.boxed-list, scrolledwindow > viewport > list, entry, spinbutton {
  background-color: alpha(@view_bg_color, 0.45);
}
.sidebar, placessidebar, stacksidebar, .navigation-sidebar, .sidebar-pane {
  background-color: alpha(@sidebar_bg_color, 0.4);
}
list row, listview row, .card, frame > border { background-color: transparent; }
/* menus, popovers, tooltips and dialogs stay solid: they float over busy content */
popover > contents, popover.background > contents, menu, .menu, .context-menu, tooltip,
tooltip.background, messagedialog, dialog.background, window.dialog {
  background-color: @popover_bg_color;
}
"""


def gtk_css(p, dark, glass):
    """GTK 3 (adw-gtk3) and GTK 4 (libadwaita) read the same named colours."""
    a = p["accent"]
    colours = {
        "accent_color": p["accent_text"], "accent_bg_color": a, "accent_fg_color": p["on_accent"],
        "destructive_color": p["ansi"][9] if dark else p["ansi"][1],
        "destructive_bg_color": p["ansi"][1], "destructive_fg_color": "#FFFFFF",
        "success_color": p["ansi"][2], "warning_color": p["ansi"][3], "error_color": p["ansi"][1],
        "window_bg_color": p["paper"], "window_fg_color": p["ink"],
        "view_bg_color": p["sheet"], "view_fg_color": p["ink"],
        "headerbar_bg_color": p["paper2"], "headerbar_fg_color": p["ink"],
        "headerbar_border_color": p["ink"], "headerbar_backdrop_color": p["paper"],
        "headerbar_shade_color": "rgba(0, 0, 0, 0.5)" if dark else rgba(p["ink"], 0.12),
        "card_bg_color": p["sheet"], "card_fg_color": p["ink"],
        "card_shade_color": "rgba(0, 0, 0, 0.4)" if dark else rgba(p["ink"], 0.10),
        "dialog_bg_color": p["sheet"] if dark else p["paper"], "dialog_fg_color": p["ink"],
        "popover_bg_color": p["sheet"], "popover_fg_color": p["ink"],
        "sidebar_bg_color": p["paper2"], "sidebar_fg_color": p["ink"],
        "shade_color": "rgba(0, 0, 0, 0.35)" if dark else rgba(p["ink"], 0.08),
        "scrollbar_outline_color": "rgba(0, 0, 0, 0.5)" if dark else "rgba(255, 255, 255, 0.5)",
        # older GTK 3 themes and apps look for these
        "theme_bg_color": p["paper"], "theme_fg_color": p["ink"],
        "theme_base_color": p["sheet"], "theme_text_color": p["ink"],
        "theme_selected_bg_color": a, "theme_selected_fg_color": p["on_accent"],
        # the raw palette under stable names, for your own styles in gtk.css (see README)
        "ws_paper": p["paper"], "ws_paper2": p["paper2"], "ws_sheet": p["sheet"], "ws_ink": p["ink"],
        "ws_muted": p["muted"], "ws_accent": a, "ws_accent_text": p["accent_text"],
        "ws_on_accent": p["on_accent"], "ws_shadow": "#000000" if dark else p["ink"],
    }
    ansi_names = ("black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
                  "bright_black", "bright_red", "bright_green", "bright_yellow", "bright_blue",
                  "bright_magenta", "bright_cyan", "bright_white")
    colours.update({f"ws_ansi_{name}": value for name, value in zip(ansi_names, p["ansi"])})
    css = "/* trpStrata — generated from your wallpaper; changes are overwritten */\n"
    css += "".join(f"@define-color {k} {v};\n" for k, v in colours.items())
    # the desktop-icons window lies over the wallpaper and must stay clear
    css += "\nwindow.desktopwindow { background-color: transparent; }\n"
    if glass:
        css += GLASS
    return css
