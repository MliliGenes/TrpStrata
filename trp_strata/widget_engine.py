"""Headless widget orchestration. The host supplies main-loop scheduling and rendering."""
from dataclasses import dataclass, field, replace
import logging
import threading

from .components import component_scope, resolve

log = logging.getLogger(__name__)


def handler(function):
    """Expose a controller method to declarative events."""
    function.widget_handler = True
    return function


class Controller:
    def mount(self, ctx):
        pass

    def props_changed(self, ctx, previous):
        pass

    def unmount(self, ctx):
        pass


@dataclass(frozen=True)
class Definition:
    controller: object
    view: object
    defaults: dict = field(default_factory=dict)


@dataclass
class Instance:
    id: str
    definition: object
    props: dict
    controller: object
    state: dict = field(default_factory=dict)
    models: dict = field(default_factory=dict)
    cleanup: list = field(default_factory=list)
    tasks: dict = field(default_factory=dict)
    tree: object = None
    dirty: bool = True
    alive: bool = True


class Context:
    def __init__(self, engine, instance):
        self.engine, self.instance = engine, instance

    @property
    def props(self):
        return self.instance.props

    @property
    def state(self):
        return self.instance.state

    def set_state(self, **changes):
        if self.instance.alive and any(key not in self.state or self.state[key] != value
                                       for key, value in changes.items()):
            self.instance.state = {**self.state, **changes}
            self.invalidate()

    def invalidate(self):
        self.engine.invalidate(self.instance.id)

    def on_cleanup(self, callback):
        self.instance.cleanup.append(callback)
        return callback

    def model(self, key, factory):
        if key not in self.instance.models:
            self.instance.models[key] = factory()
        return self.instance.models[key]

    def every(self, milliseconds, callback):
        if type(milliseconds) is not int or milliseconds < 1:
            raise ValueError("Timer interval must be a positive integer in milliseconds")

        def tick():
            if not self.instance.alive:
                return False
            try:
                callback()
            except Exception:
                log.exception("Widget %s timer failed", self.instance.id)
            return True

        token = self.engine.repeat(milliseconds, tick)
        self.on_cleanup(lambda: self.engine.cancel(token))
        return token

    def task(self, key, work, done, error=None):
        """Run blocking work off-thread. Latest result per key wins; callbacks run on main."""
        token = object()
        self.instance.tasks[key] = token

        def deliver(value, failed):
            if not self.instance.alive or self.instance.tasks.get(key) is not token:
                return False
            self.instance.tasks.pop(key, None)
            try:
                if failed:
                    if error:
                        error(value)
                    else:
                        log.error("Widget %s task %s failed: %s", self.instance.id, key, value)
                else:
                    done(value)
            except Exception:
                log.exception("Widget %s task callback failed", self.instance.id)
            return False

        def run():
            try:
                value, failed = work(), False
            except Exception as exc:
                value, failed = exc, True
            self.engine.defer(lambda: deliver(value, failed))

        thread = threading.Thread(target=run, daemon=True, name=f"widget-{self.instance.id}-{key}")
        thread.start()
        return thread


class WidgetEngine:
    def __init__(self, *, defer, repeat, cancel, on_render, validate=None):
        self.defer, self.repeat, self.cancel = defer, repeat, cancel
        self.on_render = on_render
        self.validate = validate
        self.instances = {}
        self.pending = set()
        self.scheduled = None
        self.closed = False

    def mount(self, widget_id, definition, props):
        old = self.instances.get(widget_id)
        effective = {**(definition.defaults if isinstance(definition, Definition) else {}), **props}
        if old and (old.definition is definition or (
                isinstance(definition, Definition) and isinstance(old.definition, Definition)
                and old.definition.controller is definition.controller)):
            changed = old.definition is not definition or old.props != effective
            previous = old.props
            old.definition, old.props = definition, effective
            if previous != effective and old.controller:
                old.controller.props_changed(Context(self, old), previous)
            if changed:
                self.invalidate(widget_id)
            return old
        controller = definition.controller() if isinstance(definition, Definition) else None
        instance = Instance(widget_id, definition, effective, controller)
        self.instances[widget_id] = instance
        ctx = Context(self, instance)
        try:
            if controller:
                controller.mount(ctx)
            else:
                # Compatibility controllers preserve existing scoped models and polling.
                ctx.every(1000, ctx.invalidate)
            # A replacement must mount and produce a valid tree before retiring its predecessor.
            self.invalidate(widget_id)
            self.render(widget_id)
        except Exception:
            self.remove(widget_id)
            if old:
                self.instances[widget_id] = old
                self.invalidate(widget_id)
            raise
        if old:
            self._dispose(old)
        return instance

    def invalidate(self, widget_id):
        instance = self.instances.get(widget_id)
        if self.closed or instance is None or not instance.alive:
            return
        instance.dirty = True
        self.pending.add(widget_id)
        if self.scheduled is None:
            self.scheduled = self.defer(self.flush)

    def flush(self):
        self.scheduled = None
        pending, self.pending = self.pending, set()
        if not self.closed and pending:
            self.on_render(pending)
        return False

    def dispatch(self, widget_id, name, event=None):
        instance = self.instances.get(widget_id)
        if instance is None or not instance.alive:
            return
        method = getattr(instance.controller, name, None)
        if not callable(method) or not getattr(method, "widget_handler", False):
            raise ValueError(f"Widget {widget_id}: unknown handler {name!r}")
        try:
            method(Context(self, instance), event or {})
        except Exception:
            log.exception("Widget %s handler %s failed", widget_id, name)

    def render(self, widget_id):
        instance = self.instances[widget_id]
        if not instance.dirty and instance.tree is not None:
            return instance.tree
        try:
            with component_scope(instance.models):
                if isinstance(instance.definition, Definition):
                    from .widget_views import build_view
                    view = instance.definition.view
                    ctx = Context(self, instance)
                    tree = view(ctx) if callable(view) else build_view(view, ctx)
                else:
                    tree = instance.definition(**instance.props)
                tree = resolve(tree)
                if self.validate is not None:
                    self.validate(tree)
            if instance.controller is None:
                tree = self._legacy_events(instance, tree)
            instance.tree = tree
        except Exception:
            if instance.tree is None:
                raise
            log.exception("Widget %s: keeping last working view", widget_id)
        instance.dirty = False
        return instance.tree

    def _legacy_events(self, instance, tree):
        props = dict(tree.props)
        for name in ("on_click", "on_change", "on_submit"):
            if props.get(name) is not None:
                callback = props[name]

                def dispatch(*args, callback=callback):
                    if instance.alive:
                        try:
                            callback(*args)
                        except Exception:
                            log.exception("Widget %s callback failed", instance.id)
                        finally:
                            self.invalidate(instance.id)

                props[name] = dispatch
        return replace(tree, props=props, children=tuple(self._legacy_events(instance, child)
                                                        for child in tree.children))

    def remove(self, widget_id):
        instance = self.instances.pop(widget_id, None)
        self.pending.discard(widget_id)
        if instance is None:
            return
        self._dispose(instance)

    def _dispose(self, instance):
        widget_id = instance.id
        instance.alive = False
        instance.tasks.clear()
        if instance.controller:
            try:
                instance.controller.unmount(Context(self, instance))
            except Exception:
                log.exception("Widget %s unmount failed", widget_id)
        for cleanup in reversed(instance.cleanup):
            try:
                cleanup()
            except Exception:
                log.exception("Widget %s cleanup failed", widget_id)
        for model in instance.models.values():
            try:
                close = getattr(model, "close", None)
                if close:
                    close()
            except Exception:
                log.exception("Widget %s model cleanup failed", widget_id)
        instance.models.clear()

    def close(self):
        self.closed = True
        if self.scheduled is not None:
            self.cancel(self.scheduled)
            self.scheduled = None
        for widget_id in tuple(self.instances):
            self.remove(widget_id)
