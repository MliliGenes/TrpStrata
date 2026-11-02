"""Declarative JSON views. Bindings are data paths, never executable expressions."""
import inspect

from . import components
from .widget_engine import Controller, Definition
from .widget_styles import validate as validate_style

COMPONENTS = {name: getattr(components, name) for name in (
    "Box", "Column", "Row", "Grid", "Text", "Image", "Icon", "Button", "Progress", "Ring", "Search", "Slider")}
CONTAINERS = {"Box", "Column", "Row", "Grid", "Ring"}
EVENTS = {"Button": {"click": "on_click"}, "Search": {"change": "on_change", "submit": "on_submit"},
          "Slider": {"change": "on_change"}}


def binding(value, scope):
    if isinstance(value, dict):
        if "$bind" in value:
            if set(value) != {"$bind"} or not isinstance(value["$bind"], str):
                raise ValueError("A binding must contain only a $bind path")
            current = scope
            for part in value["$bind"].split("."):
                if isinstance(current, dict) and part in current:
                    current = current[part]
                elif isinstance(current, (list, tuple)) and part.isdigit() and int(part) < len(current):
                    current = current[int(part)]
                else:
                    raise ValueError(f"Unknown binding: {value['$bind']}")
            return current
        return {key: binding(item, scope) for key, item in value.items()}
    if isinstance(value, list):
        return [binding(item, scope) for item in value]
    return value


def validate_view(node, controller=Controller, path="view", depth=0):
    if depth > 64 or not isinstance(node, dict):
        raise ValueError(f"{path}: expected a component object (maximum depth 64)")
    if "repeat" in node:
        if set(node) != {"repeat", "key", "template"} or not isinstance(node["key"], str):
            raise ValueError(f"{path}: repeat requires items binding, key field and template")
        validate_view(node["template"], controller, f"{path}.template", depth + 1)
        return
    name = node.get("type")
    if name not in COMPONENTS:
        raise ValueError(f"{path}: unknown component {name!r}")
    factory = COMPONENTS[name]
    parameters = inspect.signature(factory).parameters
    allowed = set(parameters) | {"style", "type", "events", "children"}
    unknown = set(node) - allowed
    callbacks = {"on_click", "on_change", "on_submit"} & set(node)
    if unknown or callbacks:
        raise ValueError(f"{path}: unsupported fields {sorted(unknown | callbacks)}; use events for handlers")
    if "children" in node and name not in CONTAINERS:
        raise ValueError(f"{path}: {name} cannot contain children")
    events = node.get("events", {})
    if not isinstance(events, dict):
        raise ValueError(f"{path}.events: expected an object")
    for event, target in events.items():
        if event not in EVENTS.get(name, {}):
            raise ValueError(f"{path}: {name} does not support {event!r}")
        handler_name = target.get("handler") if isinstance(target, dict) else target
        if not isinstance(handler_name, str):
            raise ValueError(f"{path}: handler must be a name")
        method = getattr(controller, handler_name, None)
        if not callable(method) or not getattr(method, "widget_handler", False):
            raise ValueError(f"{path}: unknown handler {handler_name!r}")
        if isinstance(target, dict) and set(target) - {"handler", "args"}:
            raise ValueError(f"{path}: event accepts only handler and args")
    supplied = set(node) | {EVENTS[name][event] for event in events}
    required = {key for key, parameter in parameters.items()
                if parameter.default is inspect.Parameter.empty
                and parameter.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)}
    if required - supplied:
        raise ValueError(f"{path}: missing required properties/events {sorted(required - supplied)}")
    children = node.get("children", [])
    if not isinstance(children, list):
        raise ValueError(f"{path}.children: expected a list")
    for index, child in enumerate(children):
        validate_view(child, controller, f"{path}.children[{index}]", depth + 1)
    style = node.get("style", {})
    if not isinstance(style, dict):
        raise ValueError(f"{path}.style: expected an object")
    # Static styles fail during loading; bound styles are checked after resolution.
    static = {key: value for key, value in style.items() if not isinstance(value, dict)}
    try:
        validate_style(static)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{path}.style: {error}") from error


def definition(document, controllers):
    if not isinstance(document, dict) or set(document) - {"version", "controller", "props", "view"}:
        raise ValueError("Widget document accepts version, controller, props and view")
    if document.get("version", 1) != 1:
        raise ValueError("Unsupported widget document version")
    name = document.get("controller", "static")
    if name not in controllers:
        raise ValueError(f"Unknown controller: {name!r}")
    controller = controllers[name]
    validate_view(document.get("view"), controller)
    defaults = document.get("props", {})
    if not isinstance(defaults, dict) or "config" in defaults:
        raise ValueError("Widget props must be an object; config is supplied by the host")
    return Definition(controller, document["view"], defaults)


def build_view(node, ctx, scope=None, path="view"):
    scope = scope or {"state": ctx.state, "props": ctx.props}
    try:
        if "repeat" in node:
            items = binding(node["repeat"], scope)
            if not isinstance(items, (list, tuple)):
                raise ValueError("repeat binding must resolve to a list")
            result = []
            from dataclasses import replace
            for index, item in enumerate(items):
                if not isinstance(item, dict) or node["key"] not in item:
                    raise ValueError("Repeated items must have the declared key field")
                child = build_view(node["template"], ctx, {**scope, "item": item, "index": index}, path + ".template")
                result.append(replace(child, key=item[node["key"]]))
            return result
        name = node["type"]
        props = {key: binding(value, scope) for key, value in node.items()
                 if key not in ("type", "children", "events")}
        for event, target in node.get("events", {}).items():
            target = binding(target, scope)
            handler_name = target["handler"] if isinstance(target, dict) else target
            args = target.get("args") if isinstance(target, dict) else None

            def callback(value=None, event=event, handler_name=handler_name, args=args):
                if ctx.instance.alive and ctx.engine.instances.get(ctx.instance.id) is ctx.instance:
                    ctx.engine.dispatch(ctx.instance.id, handler_name, {"type": event, "value": value, "args": args})

            props[EVENTS[name][event]] = callback
        children = [build_view(child, ctx, scope, f"{path}.children[{index}]")
                    for index, child in enumerate(node.get("children", []))]
        if name == "Ring":
            return components.Ring(props.pop("value"), *children, **props)
        return COMPONENTS[name](*children, **props) if name in CONTAINERS else COMPONENTS[name](**props)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{path}: {error}") from error
