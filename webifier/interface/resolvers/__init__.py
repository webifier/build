from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import Context, Resolver
from .builtins import (
    Asset,
    Baseurl,
    Count,
    Env,
    Exclude,
    Filter,
    Flatten,
    Glob,
    Group,
    Limit,
    Load,
    Map,
    Md,
    Now,
    Offset,
    Ref,
    Reverse,
    Sort,
    Unique,
)
from .engine import Engine, ResolverLike

# ── default engine with all built-in resolvers ────────────────────────────

_engine = Engine()

_BUILTINS: dict[str, Resolver] = {
    # sources
    "load": Load(),
    "glob": Glob(),
    "env": Env(),
    "ref": Ref(),
    "now": Now(),
    "baseurl": Baseurl(),
    "asset": Asset(),
    "md": Md(),
    # transforms
    "sort": Sort(),
    "reverse": Reverse(),
    "limit": Limit(),
    "offset": Offset(),
    "filter": Filter(),
    "exclude": Exclude(),
    "flatten": Flatten(),
    "unique": Unique(),
    "map": Map(),
    "count": Count(),
    "group": Group(),
}

for _name, _resolver in _BUILTINS.items():
    _engine.register(_name, _resolver)

# ── public API ────────────────────────────────────────────────────────────


def register_resolver(name: str, resolver: ResolverLike) -> None:
    """Register any callable as a resolver on the default engine.

    *resolver* can be:

    * A :class:`Resolver` subclass instance (dispatches via ``__call__``).
    * A plain function with signature ``(arg, ctx)`` for sources
      or ``(data, arg, ctx)`` for transforms.
    * A lambda.
    """
    _engine.register(name, resolver)


def register_source(name: str) -> Callable:
    """Decorator — register a source function ``(arg, ctx) -> value``.

    Example::

        @register_source("echo")
        def echo(arg: str, ctx: Context) -> str:
            return arg
    """

    def decorator(fn: Callable) -> Callable:
        _engine.register(name, fn)
        return fn

    return decorator


def register_transform(name: str) -> Callable:
    """Decorator — register a transform function ``(data, arg, ctx) -> value``.

    Example::

        @register_transform("take_first")
        def take_first(data, arg: str, ctx: Context):
            return data[: int(arg)] if isinstance(data, list) else data
    """

    def decorator(fn: Callable) -> Callable:
        _engine.register(name, fn)
        return fn

    return decorator


def expand(
    data: Any,
    root: dict | None = None,
    current: dict | None = None,
) -> Any:
    """Expand ``${}`` interpolations in *data* using the default engine."""
    return _engine.expand(data, root, current)


__all__ = [
    "Context",
    "Engine",
    "Resolver",
    "expand",
    "register_resolver",
    "register_source",
    "register_transform",
]
