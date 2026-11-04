# Style widgets with utility classes

Use predefined classes instead of writing CSS. These are Tailwind-inspired utilities
for native GTK 3 widgets, not Tailwind itself. No npm, build step or CSS file is needed.
Classes work in JSON views, Python components and desktop layout entries, and reload
live through the existing widget/layout watchers.

## The actual stylesheet reference

[`trp_strata/styles/widgets.css`](../trp_strata/styles/widgets.css) contains the real
class definitions in its **WIDGET UTILITY CATALOGUE** section, like a readable,
GTK-native `tailwind.css`:

```css
.text-2xl { font-size: 24px; }
.rounded-xl { border-radius: 12px; }
.text-accent { color: @ws_accent; }
```

GTK loads those definitions directly; visual values are not duplicated in a Python
styling registry. Python only indexes the classes for validation and implements native
layout operations that GTK CSS cannot express, such as gaps, grid tracks, alignment,
wrapping and size requests. Those layout classes are also listed in the catalogue's
reference comment. The file is intentionally readable rather than minified.

All twelve built-in views use **only registered utility classes**. They no longer emit
widget-specific names such as `clock-hours`, `metric-value`, `notes-text`, or
`button-primary`. Calendar highlights use conditional utilities; controls use explicit
state/theme utilities. Shared card surfaces and GTK framework hooks (such as
`desktop-widget`, slider internals and the ring's drawing area) remain internal.

Old widget-specific CSS selectors remain solely for older personal copies and legacy
Python views. Your saved layouts and personal widget copies are not rewritten. If your
own CSS targeted an old built-in class, retarget it to a utility or stable card ID, or
customize a copied view instead.

Use the bundled stylesheet as a reference, not your personal override file.
`~/.config/trpstrata/widgets.css` remains an optional, live-reloading override layer.
Maintainers can refresh the finite catalogue with `python3 tools/build-widget-utilities.py`;
users do not need to run it.

## Quick start

Copy a widget so your edits survive updates:

```sh
trpstrata widget copy Notes my_notes
trpstrata widget add my_notes
```

Edit `~/.config/trpstrata/widgets/my_notes/view.json` (`XDG_CONFIG_HOME` is respected).
For example, replace its view with:

```json
{
  "version": 1,
  "view": {
    "type": "Column",
    "class_name": "gap-3",
    "children": [
      {
        "type": "Text",
        "text": {"$bind": "state.title"},
        "class_name": "text-xl font-bold text-accent self-start text-left"
      },
      {
        "type": "Text",
        "text": {"$bind": "state.text"},
        "class_name": "text-sm text-primary text-wrap self-start text-left",
        "max_width_chars": 25
      }
    ]
  }
}
```

The adjacent Notes controller still supplies the title and text. Only the presentation
changes; editing classes does not reset controller state.

To style the **outer card**, change that instance's `class_name` in
`~/.config/trpstrata/layout.json`. Keep its other placement fields:

```json
{
  "id": "my_notes",
  "component": "my_notes",
  "class_name": "p-4 bg-surface rounded-xl border border-muted shadow-sm"
}
```

This is one entry inside the layout's `widgets` array, not the entire layout document.
Classes on a view node style that node, not its surrounding desktop card.

Python components use the same classes:

```python
Column(
    Text("Hello", class_name="text-2xl font-bold text-accent"),
    Text("No CSS needed", class_name="text-sm text-muted"),
    class_name="p-4 gap-2 rounded-xl bg-surface",
)
```

## Class reference

### Spacing and size

One spacing unit is **4 logical pixels**: `p-4` is 16px, `gap-2.5` is 10px.
`px` as a size means one pixel (`p-px`, `w-px`), not horizontal padding.

Available sizes:

```text
0 0.5 1 1.5 2 2.5 3 3.5 4 5 6 7 8 9 10 11 12 14 16
20 24 28 32 36 40 44 48 52 56 60 64 72 80 96 px
```

| Classes | Effect |
| --- | --- |
| `p-*`, `m-*` | Padding or margin on all edges |
| `px-*`, `py-*`, `mx-*`, `my-*` | Horizontal or vertical edges |
| `pt-*`, `pr-*`, `pb-*`, `pl-*` | Individual padding edges |
| `mt-*`, `mr-*`, `mb-*`, `ml-*` | Individual margin edges |
| `gap-*` | Box spacing, or both grid gaps |
| `gap-x-*`, `gap-y-*` | Grid column or row gaps |
| `w-*`, `h-*`, `size-*` | Width, height, or both size requests |
| `min-w-*`, `min-h-*` | Minimum width or height |

Sizes are native GTK requests, not clipping bounds; content minimums still apply.
Saved desktop dimensions remain in `layout.json`. Utilities use logical pixels,
unless they contain `-em-`; fixed-pixel utilities are not multiplied by the card's
font-scale setting.

### Relative sizes for scalable cards

Built-in widgets use `em` utilities to preserve their existing scale behavior:

```text
text-em-0.72   min-w-em-18   min-h-em-14   rounded-em-0.5
px-em-0.25     py-em-0.55    pt-em-0.15    ml-em-0.45
```

`text-em-N`, `min-w-em-N`, `min-h-em-N`, `rounded-em-N`, and all padding/margin
families accept this finite set of `N` values:

```text
0 0.15 0.2 0.25 0.35 0.45 0.5 0.55 0.72 0.74 0.76 0.78 0.8 0.82
0.84 0.85 0.9 1 1.05 1.1 1.2 1.35 1.5 1.75 1.8 2 2.4 3 3.25 3.8 4
4.35 6 12 13 14 15 16 17 18
```

Font sizes are relative to the parent font; padding, margins, radii and minimum sizes
use that widget's computed font size, following GTK's `em` semantics.

### Typography

| Classes | Effect |
| --- | --- |
| `text-xs`, `text-sm`, `text-base`, `text-lg`, `text-xl` | Font sizes 12, 14, 16, 18, 20px |
| `text-2xl` through `text-9xl` | Font sizes 24, 30, 36, 48, 60, 72, 96, 128px |
| `font-thin`, `font-extralight`, `font-light`, `font-normal` | Weights 100, 200, 300, 400 |
| `font-medium`, `font-semibold`, `font-bold`, `font-extrabold`, `font-black` | Weights 500–900 |
| `font-sans`, `font-mono`, `font-serif` | Font families with installed-font fallbacks |
| `font-body`, `font-display` | Body/display families from the configured widget font preset |
| `tracking-tighter`, `tracking-tight`, `tracking-normal`, `tracking-wide`, `tracking-widest` | Letter spacing −0.035em, −0.02em, 0, 0.03em, 0.10em |
| `italic`, `not-italic` | Font style |
| `text-left` / `text-start`, `text-center`, `text-right` / `text-end` | Label alignment within its allocation |
| `text-wrap`, `text-nowrap` | Label word wrapping |

### Colours

Use `text-COLOR`, `bg-COLOR`, or `border-COLOR`:

| Colour | Palette token |
| --- | --- |
| `primary` | Main text (`@ws_ink`) |
| `muted` | Secondary text (`@ws_muted`) |
| `accent` | Wallpaper accent (`@ws_accent`) |
| `on-accent` | Text on accent (`@ws_on_accent`) |
| `surface` | Card surface (`@ws_sheet`) |
| `background` | Desktop background (`@ws_paper`) |
| `red`, `green`, `yellow`, `blue`, `magenta`, `cyan` | Wallpaper-derived ANSI colours |
| `transparent`, `white`, `black` | Fixed transparent/white/black values |

Semantic colours follow palette changes automatically. For an accent button, combine
`bg-accent text-on-accent`. `text-primary` means main text, not the accent colour.

`text-inherit` follows the parent colour. Plain `text-primary`/`text-muted`/`text-accent`
always use their named palette token. Compose theme variants instead of widget-specific
colour classes: `text-muted red:text-on-accent/76` or
`text-primary light:text-muted red:text-on-accent/76`.

`bg-COLOR/N`, `border-COLOR/N` and `text-COLOR/N` add palette opacity for `primary`,
`accent` and `on-accent`. Supported percentages are
`5.5 6 7 8 9 10 12 14 16 18 22 24 38 42 55 76`.
`bg-accent-soft` / `border-accent-soft` and `bg-accent-strong` / `border-accent-strong`
mix the accent toward on-accent by 12% and 22%. `bg-accent-hover` /
`border-accent-hover` use the shared red-card hover colour.

The older `text-theme-*` helpers remain available for compatibility but are not used by
built-in views.

### Borders and shadows

| Classes | Effect |
| --- | --- |
| `rounded-none`, `rounded-sm`, `rounded`, `rounded-md` | Radius 0, 2, 4, 6px |
| `rounded-lg`, `rounded-xl`, `rounded-2xl`, `rounded-3xl`, `rounded-full` | Radius 8, 12, 16, 24, 9999px |
| `border` / `border-1`, `border-0`, `border-2`, `border-4`, `border-8` | Solid border width |
| `border-solid`, `border-dashed`, `border-dotted`, `border-none` | Border style |
| `shadow-none`, `shadow-sm`, `shadow`, `shadow-lg` | Native box shadows |

Use `border border-muted` to set both width and colour. `rounded-full` sets a large
radius; GTK does not automatically crop images or custom drawing to that radius.

### Control states, theme variants and GTK subnodes

The finite catalogue includes native state utilities, for example:

```text
bg-transparent border-primary/18 hover:bg-primary/6 hover:border-primary/24
bg-accent text-on-accent hover:bg-accent-soft active:bg-accent-strong
light:focus:border-accent red:disabled:text-on-accent/55
label:font-medium label:text-em-0.84
trough:bg-primary/10 progress:bg-accent red:progress:bg-on-accent
```

- `hover:`, `active:`, `focus:` and `disabled:` target GTK widget states.
- `light:` and `red:` target card variants and can combine with state prefixes.
- `label:` styles a button's internal label without shrinking its own dimensions.
- `trough:` and `progress:` style native progress-bar nodes. Their finite set includes
  `min-h-em-0.35`, `bg-primary/10`, `bg-accent`, `border-0`, `rounded-full`, `shadow-none`,
  and red-theme fill variants.

Only combinations explicitly defined in `widgets.css` are supported; this is not a JIT
compiler that accepts arbitrary prefixes. State utilities cover the palette/opacity
and border/text properties needed by built-in controls. Replace a state's classes to
customize that state; changing a base class does not override an explicit state class.

### Native layout

| Classes | Effect |
| --- | --- |
| `self-start`, `self-center`, `self-end`, `self-fill` | This widget's horizontal alignment |
| `vself-start`, `vself-center`, `vself-end`, `vself-fill` | This widget's vertical alignment |
| `grow`, `grow-0` | Horizontal GTK expansion and existing box packing behavior |
| `vgrow`, `vgrow-0` | Vertical GTK expansion |
| `grid-cols-N`, `grid-rows-N` | Equal fractional tracks on a `Grid` |
| `col-span-N`, `row-span-N` | Child spans |
| `col-start-N`, `row-start-N` | Child placement, starting at **1** |

`N` ranges from 1 to 12. Use `Row`, `Column` or `Grid` for container types;
`flex`, `grid` and `items-center` are not utilities. Use the `self-*` classes on children
instead. `gap-x-*`/`gap-y-*` apply only to grids, and `text-*` alignment/wrapping
applies to `Text` labels. Layout utilities follow the existing native engine contract,
not browser flexbox semantics.

## Conflicts, custom classes and validation

- Visual utilities follow the **CSS cascade and stylesheet order**, like Tailwind;
  changing the order of names in `class_name` does not change CSS precedence.
  Replace conflicting classes instead of accumulating them. Native layout utilities
  are resolved left to right, since they are GTK operations rather than CSS rules.
- Precedence is: base widget/theme CSS → utility CSS → personal `widgets.css` overrides
  → explicit structured `style`. Removing a class restores the underlying defaults.
- Explicit `style` properties also override native layout utilities, including gap.
- Existing CSS classes can be mixed in: `notes-text text-lg text-accent`.
  Unknown unprefixed names are preserved as custom CSS classes for compatibility.
- Prefix a utility with **`u:`** for strict typo checking: `u:p-4 u:text-2xl`.
  `u:rounded-xll` reports an error with a suggested correction. You can use this
  prefix for every utility if you want a predefined-only styling workflow.
- Static JSON classes are checked when loaded; bound `class_name` strings are checked
  after binding. Invalid edits retain the last working definition/tree and are logged
  through the existing widget error handling.

To combine fixed classes with a binding, use string fragments:

```json
"class_name": ["text-em-0.74 grow", {"$bind": "item.class"}]
```

Fragments can also be class-to-boolean maps, which keep visual decisions in the view
rather than constructing CSS class names in a controller. The calendar uses this:

```json
"class_name": [
  "text-em-0.74 grow",
  {
    "text-muted": {"$bind": "item.ordinary"},
    "bg-accent/14 text-primary border border-accent/42 rounded-em-0.45": {"$bind": "item.today"}
  }
]
```

Map values must resolve to actual booleans, not truthy strings or numbers. Selected
classes and string fragments are joined with spaces; no executable expressions run.

This is a finite utility set. Arbitrary values (`p-[13px]`), negative margins,
responsive variants (`md:`), arbitrary state combinations, percentages (`w-full`), transforms,
absolute positioning and browser flexbox are not implemented. Use existing structured
`style` or GTK CSS for advanced overrides if needed. Legacy views and CSS continue working.
