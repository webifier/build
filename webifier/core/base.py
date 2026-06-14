from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from .builder import Builder

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[RendererModule]] = {}


def register(name: str):
    """Class decorator — register a RendererModule under *name*."""

    def decorator(cls: type[RendererModule]):
        _REGISTRY[name] = cls
        return cls

    return decorator


def _renderer_class(renderer: str | type[RendererModule]) -> type[RendererModule]:
    cls = renderer
    if isinstance(renderer, str):
        module_path, class_name = renderer.rsplit(".", 1)
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)

    if not isinstance(cls, type) or not issubclass(cls, RendererModule):
        raise TypeError(
            f"Renderer '{renderer}' must point to a RendererModule subclass, got {cls!r}."
        )
    return cls


def register_renderer(
    name: str,
    renderer: str | type[RendererModule],
    *,
    override: bool = True,
) -> None:
    """Register a renderer class under *name*.

    This is the imperative equivalent of ``@register`` and is useful for
    site-level extension configuration such as::

        config:
          extensions:
            renderers:
              resume: mypackage.renderers.ResumeRenderer
    """
    cls = _renderer_class(renderer)

    existing = _REGISTRY.get(name)
    if existing is not None and existing is not cls and not override:
        raise ValueError(
            f"Renderer '{name}' is already registered by {existing.__module__}.{existing.__name__}. "
            "Set override: true on the later extension instance to replace it."
        )
    _REGISTRY[name] = cls


def resolve_renderer(
    name: str,
    *,
    jinja_env=None,
) -> RendererModule:
    """Resolve *name* to a RendererModule instance.

    Resolution order:
      1. Registry lookup (``@register`` decorated classes)
      2. Template file lookup (``renderers/<name>.html`` in Jinja2 search path)
      3. Dotted Python import (``some.module.ClassName``)
    """
    # 1. Registry
    if name in _REGISTRY:
        return _REGISTRY[name]()

    # 2. Template file
    if jinja_env is not None:
        template_path = f"renderers/{name}.html"
        try:
            jinja_env.get_template(template_path)
            return GenericTemplateRenderer(template=template_path)
        except Exception:
            pass

    # 3. Dotted import
    if "." in name:
        module_path, class_name = name.rsplit(".", 1)
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            if isinstance(cls, type) and issubclass(cls, RendererModule):
                return cls()
        except (ImportError, AttributeError) as exc:
            raise ValueError(
                f"Could not import renderer '{name}': {exc}\n"
                f"Ensure the module is installed and the class is a RendererModule subclass."
            ) from exc

    available = sorted(_REGISTRY.keys())
    raise ValueError(
        f"Unknown renderer kind '{name}'.\n"
        f"Available: {', '.join(available)}\n"
        f"You can also:\n"
        f"  - Create templates/renderers/{name}.html\n"
        f"  - Use a dotted Python import path"
    )


# ---------------------------------------------------------------------------
# NodeContext
# ---------------------------------------------------------------------------


@dataclass
class NodeContext:
    """Immutable context passed through the rendering tree."""

    key: str = ""
    depth: int = 0
    page_url: str = ""
    search_slug: str = ""
    search_content: bool = False
    search_links: bool = False
    assets_src_dir: str | None = None
    assets_target_dir: str | None = None
    parent: NodeContext | None = field(default=None, repr=False)

    def child(self, key: str, **overrides) -> NodeContext:
        """Create a child context with incremented depth."""
        defaults = {
            "key": key,
            "depth": self.depth + 1,
            "page_url": self.page_url,
            "search_slug": self.search_slug,
            "search_content": self.search_content,
            "search_links": self.search_links,
            "assets_src_dir": self.assets_src_dir,
            "assets_target_dir": self.assets_target_dir,
            "parent": self,
        }
        defaults.update(overrides)
        return NodeContext(**defaults)


# ---------------------------------------------------------------------------
# RendererModule ABC
# ---------------------------------------------------------------------------


class RendererModule:
    """Base class for all renderers.

    Subclasses must set:
        template  — Jinja2 template path (relative to search path)
        META_KEYS — keys consumed by this renderer (not recursed into)

    And may override:
        process() — transform data before rendering (default: recurse children)
        render()  — produce HTML from processed data (default: render template)
    """

    template: ClassVar[str] = ""
    META_KEYS: ClassVar[frozenset[str]] = frozenset({"kind", "template"})

    def process(self, data: dict[str, Any], ctx: NodeContext, builder: Builder) -> dict[str, Any]:
        """Process data before rendering. Default: recursively process children."""
        processed = {}
        for key, value in data.items():
            if key in self.META_KEYS:
                processed[key] = value
                continue
            processed[key] = builder.process_node(value, ctx.child(key))
        return processed

    def render(self, data: dict[str, Any], ctx: NodeContext, builder: Builder) -> str:
        """Render processed data to HTML. Default: render via Jinja2 template."""
        if not self.template:
            raise NotImplementedError(
                f"{type(self).__name__} has no template set. "
                f"Either set the 'template' class variable or override render()."
            )
        template = builder.jinja_env.get_template(self.template)
        return template.render(
            data=data,
            ctx=ctx,
            process=lambda v, **kw: builder.process_node(v, ctx.child(kw.get("key", ""), **kw)),
            markdown=builder.render_markdown,
            baseurl=builder.base_url,
            builder=builder,
        )


# ---------------------------------------------------------------------------
# GenericTemplateRenderer
# ---------------------------------------------------------------------------


class GenericTemplateRenderer(RendererModule):
    """Wraps a Jinja2 template file as a renderer — no Python class needed.

    Used for:
      - ``kind: gallery`` when ``templates/renderers/gallery.html`` exists
      - ``template: templates/landing.html`` (inline override)
    """

    META_KEYS: ClassVar[frozenset[str]] = frozenset({"kind", "template"})

    def __init__(self, template: str = ""):
        self._template = template

    @property
    def template(self) -> str:  # type: ignore[override]
        return self._template

    @template.setter
    def template(self, value: str):
        self._template = value

    def process(self, data: dict[str, Any], ctx: NodeContext, builder: Builder) -> dict[str, Any]:
        """Pass all data through — let the template decide what to do."""
        return data
