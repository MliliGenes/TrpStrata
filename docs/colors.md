# Colour tokens

trpStrata generates a light and dark palette from the current wallpaper. The
GTK tokens are collected in [`trp_strata/styles/colors.css`](../trp_strata/styles/colors.css),
which is loaded before widget and control-panel styles.

GTK calls these `@define-color` values rather than CSS custom properties. Use
the semantic names below in `~/.config/trpstrata/widgets.css` or
`~/.config/trpstrata/app.css`:

| Swatch | GTK token | Use |
|---|---|---|
| <span style="display:inline-block;width:2em;height:1em;background:#d9e2f0"></span> | `@color_background` | Main window / page background |
| <span style="display:inline-block;width:2em;height:1em;background:#c5d1e2"></span> | `@color_background_alt` | Header and alternate background |
| <span style="display:inline-block;width:2em;height:1em;background:#edf2f8"></span> | `@color_surface` | Cards, sheets and popovers |
| <span style="display:inline-block;width:2em;height:1em;background:#17202b"></span> | `@color_text` | Primary text |
| <span style="display:inline-block;width:2em;height:1em;background:#536273"></span> | `@color_text_muted` | Captions and secondary text |
| <span style="display:inline-block;width:2em;height:1em;background:#3779c9"></span> | `@color_accent` | Main accent / selected controls |
| <span style="display:inline-block;width:2em;height:1em;background:#245ea8"></span> | `@color_accent_text` | Accent text on light surfaces |
| <span style="display:inline-block;width:2em;height:1em;background:#ffffff"></span> | `@color_on_accent` | Text on accent backgrounds |

The swatches above are illustrative; the actual values change with the
wallpaper. The application shows the current light and dark swatches under
**Appearance → Wallpaper palette**.

The original generated names remain available too:
`@ws_paper`, `@ws_paper2`, `@ws_sheet`, `@ws_ink`, `@ws_muted`, `@ws_accent`,
`@ws_accent_text`, `@ws_on_accent`, and `@ws_shadow`.

## Accent and terminal colours

The complete wallpaper-derived ANSI set is available as
`@color_black`, `@color_red`, `@color_green`, `@color_yellow`, `@color_blue`,
`@color_magenta`, `@color_cyan`, `@color_white`, and their
`@color_bright_*` variants. The underlying names are `@ws_ansi_*`.

The stylesheet also includes optional swatch classes, for example:

```css
.my-accent-preview {
  min-width: 2em;
  min-height: 2em;
  border-radius: 999px;
  background-color: @color_accent;
}

/* Equivalent helper class from colors.css: */
.my-accent-preview.trpstrata-swatch.trpstrata-swatch-accent {
  border: 2px solid @color_on_accent;
}
```

Do not edit the generated `~/.config/trpstrata/theme.css`; it is replaced
when the wallpaper or appearance mode changes.
