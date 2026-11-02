# Widget engine: editable views and controllers

All twelve built-in widget types now run through one `WidgetEngine`. Each instance
has independent state, a controller, managed resources, and a declarative view.
The desktop host still owns the transparent window, positioning, dragging, sizing,
wallpaper glass, and input regions. GTK 3 remains the widget renderer.

```text
layout.json                  widget JSON / Python controller
     │                                  │
     └─────────── WidgetEngine ──────────┘
                       │
        event → controller → state update
                       │
               batched render queue
                       │
          bindings → component tree → styles/grid
                       │
                 GTK renderer
                       │
                 desktop host
```

## Customize an existing widget

List the available built-in views and export one:

```sh
trpstrata widget list
trpstrata widget export Clock
mkdir -p ~/.config/trpstrata/widgets
trpstrata widget export Clock > ~/.config/trpstrata/widgets/Clock.json
```

The last command writes a new override; keep a copy if that file already exists.
Use `$XDG_CONFIG_HOME/trpstrata/widgets` instead when `XDG_CONFIG_HOME` is set.

Editing `Clock.json` now changes every layout instance using `"component": "Clock"`.
For an independent design, save it as `my_clock.json` and set that instance's
component to `my_clock`. Its `"controller": "clock"` still uses the built-in logic.
Delete a built-in override to restore its default view.

View edits reload live, retaining controller state when the controller class stays
the same. Invalid JSON/schema edits retain the previous definition; binding/render
errors retain the last rendered tree and are logged in the helper log. Changing
controller source replaces the controller and its state. Existing custom Python
files exporting `@component def Widget(...)` remain supported. A `.json` view takes
precedence over the same-name `.py` component.

## View format

```json
{
  "version": 1,
  "controller": "clock",
  "view": {
    "type": "Grid",
    "columns": ["1fr", "2fr"],
    "style": {"padding": 20, "gap": 12, "width": 360},
    "visible": {"$bind": "state.visible"},
    "children": [
      {
        "type": "Text",
        "key": "time",
        "text": {"$bind": "state.time"},
        "style": {"fontSize": 48, "fontWeight": 700}
      },
      {
        "type": "Text",
        "key": "date",
        "text": {"$bind": "state.date"},
        "visible": {"$bind": "state.show_date"},
        "style": {"fontSize": 18, "textAlign": "start"}
      }
    ]
  }
}
```

Supported components: `Box` (a column), `Column`, `Row`, `Grid`, `Text`, `Image`,
`Icon`, `Button`, `Progress`, `Ring`, `Search`, and `Slider`. Their ordinary props
match the Python component API, including `class_name`, `visible`, and `key`.
For icon buttons, use `Button` with `icon` and an accessible `text`/`tooltip`.

Bindings resolve paths within `state`, `props`, and, inside repeats, `item` and
`index`. They preserve types, including image bytes supplied by controllers.
There are no executable expressions: compute formatted labels and visibility
booleans in the controller. Definition-level `props` supply defaults; layout props
override them. `props.config` is supplied by the runtime.

Repeated children use stable item IDs:

```json
{
  "repeat": {"$bind": "state.items"},
  "key": "id",
  "template": {
    "type": "Button",
    "text": {"$bind": "item.label"},
    "events": {
      "click": {"handler": "choose", "args": {"$bind": "item.id"}}
    }
  }
}
```

Place repeat objects in a container's `children` array. Each item must be an object
with the declared key field; sibling keys must be unique strings or integers.

## Styles and sizing

Every primitive supports `style` in both JSON and Python:

```python
Grid(
    Text("Heading", style={"columnSpan": 2, "fontSize": 24}),
    Text("CPU"),
    Text("32%", style={"textAlign": "end"}),
    columns=["1fr", "2fr"],
    style={"padding": 20, "gap": 12, "width": 320},
)
```

| Properties | Behavior |
| --- | --- |
| `width`, `height` | GTK size requests in logical pixels; content minimums still apply |
| `minWidth`, `minHeight` | GTK CSS minimum sizes |
| `padding`, `margin` | Nonnegative pixels, or 1–4 numbers in CSS top/right/bottom/left shorthand order |
| `paddingTop/Right/Bottom/Left`, `marginTop/Right/Bottom/Left` | Individual pixel edges |
| `gap` | Row/column spacing or both grid gaps |
| `rowGap`, `columnGap` | Separate grid gaps |
| `alignSelf`, `valignSelf` | Widget alignment: `start`, `center`, `end`, `fill` |
| `expand`, `vexpand` | Horizontal/vertical GTK expansion |
| `textAlign`, `wrap` | Label alignment and wrapping |
| `fontSize`, `fontWeight`, `fontFamily`, `fontStyle` | Typography; font size is in pixels |
| `color`, `background` | Native GTK color/background values, including theme colors |
| `border`, `borderWidth`, `borderColor`, `borderStyle`, `borderRadius`, `boxShadow` | Native GTK appearance |
| `columns`, `rows` | Grid track lists (also accepted as Grid props) |
| `column`, `row`, `columnSpan`, `rowSpan` | Zero-based placement and positive spans on grid children |

Grid tracks accept pixel numbers, `"auto"`, and positive fractional weights such as
`"1fr"` and `"2fr"`. Fractional tracks divide available space by weight after
content minimums are satisfied. Fixed tracks also grow when required by content;
they do not clip controls. Missing rows are automatic. Children fill unoccupied
cells in row-major order; overlapping explicit placements are rejected. Hidden
children retain their assigned cells but contribute no size requirement.

Structured styles override component layout defaults and native theme/class CSS
on the styled widget. Removing a property restores its default. Typography can
inherit, while a descendant's explicit font/color rule takes precedence over an
inherited value. Existing `widgets.css` still supports GTK selectors and states.

Desktop card dimensions in `layout.json` control the outer frame. Structured sizes
contribute content requests; the host respects content minimums, saved dimensions,
and then desktop grid snapping. A larger saved frame can give fractional tracks
extra room. Turn desktop snap-to-grid off for pixel-level outer sizing.

This is a native GTK layout contract, not browser CSS. Maximum-size clipping,
percent dimensions, flex wrapping, transforms, and absolute positioning are not
implemented. Unsupported style keys fail validation rather than silently doing
nothing. Use numeric logical pixels for structured lengths; existing GTK CSS can
continue using GTK-supported units.

## Custom controller and events

Create `widgets/counter.py`:

```python
from trp_strata.widget_engine import Controller as BaseController, handler

class Controller(BaseController):
    def mount(self, ctx):
        ctx.set_state(count=ctx.props.get("initial", 0))

    @handler
    def increment(self, ctx, event):
        ctx.set_state(count=ctx.state["count"] + 1)
```

And `widgets/counter.json`:

```json
{
  "version": 1,
  "controller": "counter",
  "props": {"initial": 0},
  "view": {
    "type": "Column",
    "style": {"padding": 20, "gap": 12},
    "children": [
      {"type": "Text", "text": {"$bind": "state.count"}, "style": {"fontSize": 32}},
      {"type": "Button", "text": "Increase", "events": {"click": "increment"}}
    ]
  }
}
```

Add an entry with `"component": "counter"` to `layout.json`. Multiple entries get
separate counters. Only methods decorated with `@handler` are available to JSON.

Events: `Button.click`, `Search.change`, `Search.submit`, and `Slider.change`.
Search requires a `change` handler; `submit` is optional. Handlers receive
`{"type": ..., "value": ..., "args": ...}`. Change/submit carry the current value;
click has a null value. Optional `args` come from the view, including item bindings.

Controller lifecycle and context:

- `mount(ctx)`, `props_changed(ctx, previous_props)`, `unmount(ctx)`.
- `ctx.props`, `ctx.state`: read current values; use `set_state(**changes)` rather
  than mutating state. Changed values schedule a render of that instance only.
- `ctx.every(milliseconds, callback)`: managed main-thread timer.
- `ctx.on_cleanup(callback)`: register subscription/resource cleanup.
- `ctx.model(key, factory)`: retain an existing backend model; its `close()` method
  is called on removal.
- `ctx.task(key, work, done, error=None)`: background work with main-thread result
  callbacks. Latest task per key wins; results from removed instances are ignored.
  Running work is not forcibly interrupted; use cleanup for cancellable resources.
- `ctx.invalidate()`: request a render when using external mutable state.

Widget handlers and GTK updates run on the main thread. Timer/task/handler failures
are logged per instance. Resources are released when an instance is disabled,
removed, replaced, or the engine shuts down.

Built-in controllers reuse existing backend models. Polling models are sampled by
controller-owned timers; unchanged state does not rerender. Notes update on props
changes, Calendar checks every 30 seconds, and other built-ins sample every second.
Legacy Python components retain their one-second refresh through the compatibility
path. The host's lock-visibility check does not itself rebuild every widget.

## Development checks

```sh
/usr/bin/python3 -m unittest discover -s tests -p 'test_widget_engine.py'
/usr/bin/python3 tests/run_native_smoke.py
```

The native runner uses an isolated Broadway display and checks existing desktop
behavior plus structured styles, mixed fractional grid sizing, state-preserving
view reload, and event dispatch.
