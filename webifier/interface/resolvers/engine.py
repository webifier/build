from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .base import Context, Resolver
from .utils import parse_step

# Matches the *innermost* ${…} (no nested braces inside).
# Resolving inside-out naturally handles ${${ref:.key}} etc.
_INNER_RE = re.compile(r"\$\{([^{}]+)\}")

#: Anything the engine can call: a Resolver instance *or* a plain function.
ResolverLike = Resolver | Callable[..., Any]


class Engine:
    """Recursive ``${}`` resolver engine with pipe chaining.

    Any callable can be registered as a resolver:

    * A :class:`Resolver` subclass instance (dispatches via ``__call__``).
    * A plain function with signature ``(arg, ctx)`` for sources
      or ``(data, arg, ctx)`` for transforms.

    Usage::

        engine = Engine()
        engine.register("ref", RefResolver())       # class
        engine.register("echo", lambda a, c: a)     # function
        result = engine.expand({"title": "${ref:.name}", "name": "hi"})
    """

    def __init__(self) -> None:
        self._resolvers: dict[str, ResolverLike] = {}

    # -- registration ------------------------------------------------------

    def register(self, name: str, resolver: ResolverLike) -> None:
        """Register *resolver* (any callable) under *name*."""
        self._resolvers[name] = resolver

    # -- public entry point ------------------------------------------------

    def expand(
        self,
        data: Any,
        root: dict | None = None,
        current: dict | None = None,
    ) -> Any:
        """Expand all ``${}`` interpolations in *data*."""
        if root is None:
            root = data if isinstance(data, dict) else {}
        if current is None:
            current = root
        return self._walk(data, Context(root, current))

    # -- recursive walk ----------------------------------------------------

    def _walk(self, data: Any, ctx: Context) -> Any:
        if isinstance(data, str):
            return self._resolve_string(data, ctx)
        if isinstance(data, dict):
            return {
                k: self._walk(v, Context(ctx.root, data))
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [self._walk(item, ctx) for item in data]
        return data

    # -- string resolution (handles nesting) -------------------------------

    def _resolve_string(self, s: str, ctx: Context) -> Any:
        """Resolve ``${}`` expressions inside-out for nesting support.

        Iterates until no more innermost ``${…}`` remain, supporting
        patterns like ``${${ref:.key}}`` and ``${load:${ref:.file}}``.
        """
        prev = None
        while "${" in s and s != prev:
            prev = s
            m = _INNER_RE.search(s)
            if not m:
                break

            result = self._pipeline(m.group(1), ctx)

            # Full-value: the *entire* string (ignoring whitespace) is one
            # interpolation → return the resolved value with its original type
            if not s[: m.start()].strip() and not s[m.end() :].strip():
                return result

            # Partial: stringify and keep resolving remaining expressions
            text = str(result) if result is not None else ""
            s = s[: m.start()] + text + s[m.end() :]

        return s

    # -- pipeline evaluation -----------------------------------------------

    def _pipeline(self, expr: str, ctx: Context) -> Any:
        """Evaluate ``source:arg | transform:arg | …``."""
        steps = [s.strip() for s in expr.split(" | ")]

        # First step — source call: resolver(arg, ctx)
        name, arg = parse_step(steps[0])
        resolver = self._resolvers.get(name)

        if resolver:
            value = resolver(arg, ctx)
        elif not name and arg:
            # Bare ``:path`` — treat as ref
            ref = self._resolvers.get("ref")
            value = ref(arg, ctx) if ref else arg
        else:
            return expr  # unknown resolver, return raw

        # Remaining steps — transform call: resolver(data, arg, ctx)
        for step in steps[1:]:
            name, arg = parse_step(step)
            resolver = self._resolvers.get(name)
            if resolver:
                value = resolver(value, arg, ctx)

        return value
