from __future__ import annotations

import copy
import importlib
import inspect
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import metadata
from typing import TYPE_CHECKING, Any

import jinja2

from webifier.interface.resolvers import register_resolver

from .base import RendererModule, register_renderer
from .loader import register_format

if TYPE_CHECKING:
    from .builder import Builder


Hook = Callable[..., str | None]
ContentRenderer = Callable[["Builder", str, Any], str | None]
PageKeyConsumer = Callable[..., Any]


@dataclass(frozen=True)
class AssetMount:
    """A package asset directory mounted into the generated site."""

    source: str
    target: str = "assets/webifier/{instance}"


@dataclass
class ExtensionManifest:
    """Declarative registrations exported by an extension object."""

    id: str
    renderers: dict[str, str | type[RendererModule]] = field(default_factory=dict)
    content_renderers: dict[str, str | ContentRenderer] = field(default_factory=dict)
    page_keys: dict[str, str | PageKeyConsumer] = field(default_factory=dict)
    resolvers: dict[str, str | Callable] = field(default_factory=dict)
    formats: dict[str, str | Callable] = field(default_factory=dict)
    template_dirs: list[str] = field(default_factory=list)
    assets: list[AssetMount] = field(default_factory=list)
    hooks: dict[str, list[str | Hook]] = field(default_factory=dict)
    config_defaults: dict[str, Any] = field(default_factory=dict)
    default_config: dict[str, Any] = field(default_factory=dict)
    dependencies: tuple[str, ...] = ()

    def register(self, ctx: ExtensionContext) -> None:
        """Register this manifest against a builder."""
        for dependency in self.dependencies:
            if dependency not in ctx.manager.enabled_extension_ids:
                raise ValueError(
                    f"Extension '{self.id}' requires '{dependency}'. "
                    f"Enable it before instance '{ctx.instance_name}'."
                )

        for template_dir in self.template_dirs:
            ctx.add_template_dir(template_dir)

        for asset in self.assets:
            ctx.add_asset_dir(asset.source, asset.target)

        for name, renderer in self.renderers.items():
            ctx.register_renderer(name, renderer)

        for key, renderer in self.content_renderers.items():
            ctx.register_content_renderer(key, renderer)

        for key, consumer in self.page_keys.items():
            ctx.consume_page_key(key, consumer)

        for name, resolver in self.resolvers.items():
            ctx.register_resolver(name, resolver)

        for extension, loader in self.formats.items():
            ctx.register_format(extension, loader)

        for area, hooks in self.hooks.items():
            for hook in hooks:
                ctx.add_hook(area, hook)


class Extension:
    """Base class for Webifier extension packages.

    Simple extensions can define class attributes. More involved extensions can
    override ``manifest`` or ``register`` while keeping the same lifecycle.
    """

    id: str = ""
    renderers: dict[str, str | type[RendererModule]] = {}
    content_renderers: dict[str, str | ContentRenderer] = {}
    page_keys: dict[str, str | PageKeyConsumer] = {}
    resolvers: dict[str, str | Callable] = {}
    formats: dict[str, str | Callable] = {}
    template_dirs: list[str] = []
    assets: list[AssetMount] = []
    hooks: dict[str, list[str | Hook]] = {}
    config_defaults: dict[str, Any] = {}
    default_config: dict[str, Any] = {}
    dependencies: tuple[str, ...] = ()

    def manifest(self) -> ExtensionManifest:
        """Return this extension's declarative registrations."""
        if not self.id:
            raise ValueError(f"{self.__class__.__name__} must define an extension id.")
        return ExtensionManifest(
            id=self.id,
            renderers=copy.deepcopy(self.renderers),
            content_renderers=copy.deepcopy(self.content_renderers),
            page_keys=copy.deepcopy(self.page_keys),
            resolvers=copy.deepcopy(self.resolvers),
            formats=copy.deepcopy(self.formats),
            template_dirs=copy.deepcopy(self.template_dirs),
            assets=copy.deepcopy(self.assets),
            hooks=copy.deepcopy(self.hooks),
            config_defaults=copy.deepcopy(self.config_defaults),
            default_config=copy.deepcopy(self.default_config),
            dependencies=tuple(self.dependencies),
        )

    def register(self, ctx: ExtensionContext) -> None:
        """Register this extension against a builder."""
        self.manifest().register(ctx)


@dataclass
class ExtensionInstance:
    name: str
    uses: str
    config: dict[str, Any]
    override: bool = False
    reset: bool = False


@dataclass(frozen=True)
class ExtensionHookContext:
    """Context passed to extension hooks during a lifecycle phase."""

    area: str
    builder: Builder
    config: dict[str, Any]
    page: dict[str, Any] | None = None
    ctx: Any = None
    extension_id: str = ""
    instance_name: str = ""
    instance_config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RegisteredHook:
    callback: Hook
    extension_id: str
    instance_name: str
    instance_config: dict[str, Any]


@dataclass(frozen=True)
class RegisteredPageKeyConsumer:
    key: str
    callback: PageKeyConsumer
    extension_id: str
    instance_name: str
    instance_config: dict[str, Any]


class ExtensionContext:
    """Registration API exposed to an extension."""

    def __init__(
        self,
        *,
        manager: ExtensionManager,
        extension: ExtensionManifest,
        instance: ExtensionInstance,
    ) -> None:
        self.manager = manager
        self.builder = manager.builder
        self.extension = extension
        self.instance = instance
        self.instance_name = instance.name
        self.config = instance.config
        self.override = instance.override

    def _import_object(self, target: str | Callable) -> Callable:
        if not isinstance(target, str):
            return target
        module_path, object_name = target.rsplit(".", 1)
        return getattr(importlib.import_module(module_path), object_name)

    def add_template_dir(self, template_dir: str) -> None:
        loader = self.builder.jinja_env.loader
        if not isinstance(loader, jinja2.FileSystemLoader):
            return
        if template_dir not in loader.searchpath:
            loader.searchpath.append(template_dir)

    def add_asset_dir(self, source: str, target: str) -> None:
        self.manager.asset_mounts.append(
            AssetMount(source=source, target=target.format(instance=self.instance_name))
        )

    def register_renderer(self, name: str, renderer: str | type[RendererModule]) -> None:
        register_renderer(name, renderer, override=self.override)

    def register_content_renderer(self, key: str, renderer: str | ContentRenderer) -> None:
        target = self._import_object(renderer)
        existing = self.builder.content_renderers.get(key)
        if existing is not None and existing is not target and not self.override:
            raise ValueError(
                f"Content renderer '{key}' is already registered. "
                "Set override: true on the later extension instance to replace it."
            )
        self.builder.content_renderers[key] = target

    def consume_page_key(self, key: str, consumer: str | PageKeyConsumer) -> None:
        target = self._import_object(consumer)
        existing = self.manager.page_key_consumers.get(key)
        if existing is not None and existing.callback is not target and not self.override:
            raise ValueError(
                f"Page key '{key}' is already consumed by instance '{existing.instance_name}'. "
                "Set override: true on the later extension instance to replace it."
            )
        self.manager.page_key_consumers[key] = RegisteredPageKeyConsumer(
            key=key,
            callback=target,
            extension_id=self.extension.id,
            instance_name=self.instance_name,
            instance_config=copy.deepcopy(self.config),
        )

    def register_resolver(self, name: str, resolver: str | Callable) -> None:
        register_resolver(name, self._import_object(resolver))

    def register_format(self, extension: str, loader: str | Callable) -> None:
        register_format(extension, self._import_object(loader))

    def add_hook(self, area: str, hook: str | Hook) -> None:
        self.manager.hooks[area].append(
            RegisteredHook(
                callback=self._import_object(hook),
                extension_id=self.extension.id,
                instance_name=self.instance_name,
                instance_config=copy.deepcopy(self.config),
            )
        )


class ExtensionManager:
    """Loads and applies named extension instances for a builder."""

    def __init__(self, builder: Builder) -> None:
        self.builder = builder
        self.available: dict[str, type[Extension] | Extension] = {}
        self.instances: list[ExtensionInstance] = []
        self.instances_by_name: dict[str, ExtensionInstance] = {}
        self.enabled_instance_names: set[str] = set()
        self.enabled_extension_ids: set[str] = set()
        self.config_defaults: dict[str, Any] = {}
        self.config_overlays: dict[str, Any] = {}
        self.asset_mounts: list[AssetMount] = []
        self.hooks: dict[str, list[RegisteredHook]] = defaultdict(list)
        self.page_key_consumers: dict[str, RegisteredPageKeyConsumer] = {}

    def configure(self, config: dict[str, Any]) -> None:
        """Configure extension instances from a root site config."""
        self.available = self.discover()
        for instance in self._parse_instances(config):
            self._register_instance(instance)
            self.config_overlays[instance.name] = _deep_merge(
                self.config_overlays.get(instance.name, {}),
                copy.deepcopy(instance.config),
            )

    def configure_page_extensions(self, config: dict[str, Any]) -> None:
        """Register page-local extension instances before rendering that page."""
        if not self.available:
            self.available = self.discover()
        for instance in self._parse_instances(config):
            if instance.name in self.enabled_instance_names and not instance.override:
                continue
            self._register_instance(instance)

    def discover(self) -> dict[str, type[Extension] | Extension]:
        """Discover installed extension classes."""
        found: dict[str, type[Extension] | Extension] = {}

        try:
            entry_points = metadata.entry_points()
            if hasattr(entry_points, "select"):
                selected = entry_points.select(group="webifier.extensions")
            else:
                selected = entry_points.get("webifier.extensions", [])
            for ep in selected:
                found[ep.name] = ep.load()
        except Exception:
            pass

        # Editable/local development fallback when the package is on sys.path.
        try:
            registry = importlib.import_module("webifier_extensions.registry")
            for extension_id, factory in registry.EXTENSIONS.items():
                found.setdefault(extension_id, factory)
        except Exception:
            pass

        return found

    def apply_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Merge extension defaults and exported instance config into site config."""
        merged = _deep_merge(copy.deepcopy(self.config_defaults), copy.deepcopy(config))
        for key, value in self.config_overlays.items():
            merged[key] = _deep_merge(copy.deepcopy(value), copy.deepcopy(merged.get(key, {})))
        return merged

    def page_config_overlays(self, config: dict[str, Any]) -> list[tuple[str, dict[str, Any], bool]]:
        """Return instance-name config overlays exported by page-local extensions."""
        if not self.available:
            self.available = self.discover()
        overlays = []
        for instance in self._parse_instances(config):
            extension = self._load(instance.uses)
            manifest = extension.manifest()
            merged_instance_config = _deep_merge(
                copy.deepcopy(manifest.default_config),
                copy.deepcopy(instance.config),
            )
            overlays.append((instance.name, merged_instance_config, instance.reset))
        return overlays

    def render_area(self, area: str, **kwargs) -> str:
        """Render string fragments contributed by hooks in an area."""
        fragments = []
        for hook in self.hooks.get(area, []):
            rendered = self._call_hook(area, hook, **kwargs)
            if rendered:
                fragments.append(str(rendered))
        return "\n".join(fragments)

    def run_hooks(self, area: str, **kwargs) -> None:
        """Run side-effect hooks."""
        for hook in self.hooks.get(area, []):
            self._call_hook(area, hook, **kwargs)

    def consume_page_keys(
        self,
        data: dict[str, Any],
        *,
        ctx: Any = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Let extensions consume page-level keys before section rendering."""
        if not self.page_key_consumers:
            return data
        config = config or self.builder.config
        remaining = dict(data)
        for key in list(data):
            consumer = self.page_key_consumers.get(key)
            if consumer is None:
                continue
            value = remaining.pop(key, data[key])
            consumer_context = ExtensionHookContext(
                area="page_key",
                builder=self.builder,
                config=config,
                page=remaining,
                ctx=ctx,
                extension_id=consumer.extension_id,
                instance_name=consumer.instance_name,
                instance_config=copy.deepcopy(consumer.instance_config),
            )
            call_kwargs = {
                "key": key,
                "value": value,
                "data": remaining,
                "page": remaining,
                "config": config,
                "ctx": ctx,
                "hook_context": consumer_context,
                "extension_id": consumer.extension_id,
                "instance_name": consumer.instance_name,
                "instance_config": copy.deepcopy(consumer.instance_config),
            }
            result = _call_with_supported_kwargs(consumer.callback, self.builder, call_kwargs)
            if result is not None:
                extension_data = remaining.setdefault("_extension_data", {})
                if isinstance(extension_data, dict):
                    extension_data.setdefault(consumer.instance_name, {})[key] = result
        return remaining

    def _call_hook(self, area: str, hook: RegisteredHook, **kwargs):
        config = kwargs.get("config")
        if config is None:
            config = self.builder.config
        page = kwargs.get("page") or kwargs.get("data")
        hook_context = ExtensionHookContext(
            area=area,
            builder=self.builder,
            config=config,
            page=page,
            ctx=kwargs.get("ctx"),
            extension_id=hook.extension_id,
            instance_name=hook.instance_name,
            instance_config=copy.deepcopy(hook.instance_config),
        )
        call_kwargs = {
            **kwargs,
            "area": area,
            "config": config,
            "page": page,
            "hook_context": hook_context,
            "extension_id": hook.extension_id,
            "instance_name": hook.instance_name,
            "instance_config": copy.deepcopy(hook.instance_config),
        }
        return _call_with_supported_kwargs(hook.callback, self.builder, call_kwargs)

    def _load(self, extension_id: str) -> Extension:
        provider = self.available.get(extension_id)
        if provider is None:
            available = ", ".join(sorted(self.available)) or "none"
            raise ValueError(
                f"Unknown Webifier extension '{extension_id}'. "
                f"Install its package or check the 'uses' value. Available: {available}"
            )
        if isinstance(provider, Extension):
            extension = provider
        elif inspect.isclass(provider) and issubclass(provider, Extension):
            extension = provider()
        else:
            raise TypeError(
                f"Extension '{extension_id}' must expose an Extension subclass or instance."
            )
        declared_id = extension.manifest().id
        if declared_id != extension_id:
            raise ValueError(
                f"Extension entry '{extension_id}' declares id '{declared_id}'. "
                "The entry point name, registry key, and extension id must match."
            )
        return extension

    def _parse_instances(self, config: dict[str, Any]) -> list[ExtensionInstance]:
        webifier_cfg = config.get("webifier", {}) if isinstance(config, dict) else {}
        raw = webifier_cfg.get("extensions", {}) if isinstance(webifier_cfg, dict) else {}
        if not raw:
            return []
        if not isinstance(raw, dict):
            raise TypeError("config.webifier.extensions must be a mapping of named instances.")

        instances = []
        for name, value in raw.items():
            if value is False or value is None:
                continue
            if isinstance(value, str):
                value = {"uses": value}
            if not isinstance(value, dict):
                raise TypeError(f"Extension instance '{name}' must be a mapping.")
            if value.get("enabled", True) is False:
                continue
            uses = value.get("uses")
            if not uses:
                existing_instance = self.instances_by_name.get(str(name))
                if existing_instance is None:
                    raise ValueError(f"Extension instance '{name}' is missing required 'uses'.")
                uses = existing_instance.uses
            config = {
                key: copy.deepcopy(item)
                for key, item in value.items()
                if key not in {"uses", "override", "enabled", "reset"}
            }
            instances.append(
                ExtensionInstance(
                    name=str(name),
                    uses=str(uses),
                    config=config,
                    override=bool(value.get("override", False)),
                    reset=bool(value.get("reset", False)),
                )
            )
        return instances

    def _register_instance(self, instance: ExtensionInstance) -> ExtensionManifest:
        extension = self._load(instance.uses)
        manifest = extension.manifest()
        merged_instance_config = _deep_merge(
            copy.deepcopy(manifest.default_config),
            copy.deepcopy(instance.config),
        )
        instance.config.clear()
        instance.config.update(merged_instance_config)

        for dependency in manifest.dependencies:
            if dependency not in self.enabled_extension_ids:
                raise ValueError(
                    f"Extension '{manifest.id}' requires '{dependency}'. "
                    f"Enable it before instance '{instance.name}'."
                )

        ctx = ExtensionContext(manager=self, extension=manifest, instance=instance)
        extension.register(ctx)
        self.instances.append(instance)
        self.instances_by_name[instance.name] = copy.deepcopy(instance)
        self.enabled_instance_names.add(instance.name)
        self.enabled_extension_ids.add(manifest.id)
        self.config_defaults = _deep_merge(self.config_defaults, manifest.config_defaults)
        return manifest


def _deep_merge(base: Any, override: Any) -> Any:
    """Recursively merge mappings, with override values winning."""
    if isinstance(base, dict) and isinstance(override, dict):
        result = copy.deepcopy(base)
        for key, value in override.items():
            result[key] = _deep_merge(result.get(key), value)
        return result
    if override is None:
        return copy.deepcopy(base)
    return copy.deepcopy(override)


__all__ = [
    "AssetMount",
    "Extension",
    "ExtensionContext",
    "ExtensionHookContext",
    "ExtensionInstance",
    "ExtensionManifest",
    "ExtensionManager",
]


def _call_with_supported_kwargs(fn: Callable, builder: Builder, kwargs: dict[str, Any]):
    """Call a hook, filtering kwargs for simple hook signatures."""
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(builder, **kwargs)
    params = signature.parameters
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()):
        return fn(builder, **kwargs)

    supported = {
        key: value
        for key, value in kwargs.items()
        if key in params and key != "builder"
    }
    return fn(builder, **supported)
