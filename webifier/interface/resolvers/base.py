from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Context:
    """Document context passed to every resolver.

    Attributes:
        root:    The top-level document dict.
        current: The dict that *contains* the value being resolved.
    """

    root: dict
    current: dict


class Resolver:
    """Base class for resolvers — also makes every instance callable.

    The engine calls resolvers with two signatures:

    * **source**  ``resolver(arg, ctx)``  — first step in a pipeline
    * **transform**  ``resolver(data, arg, ctx)``  — subsequent steps

    ``__call__`` dispatches on argument count, so subclasses only need
    to override :meth:`source`, :meth:`transform`, or both.

    Because the protocol is just "a callable", plain functions work too::

        # source function  (arg, ctx) -> value
        def echo(arg, ctx):
            return arg

        # transform function  (data, arg, ctx) -> value
        def upper(data, arg, ctx):
            return data.upper() if isinstance(data, str) else data

        engine.register("echo", echo)
        engine.register("upper", upper)
    """

    def __call__(self, *args: Any) -> Any:
        """Dispatch to :meth:`source` or :meth:`transform` by arity."""
        if len(args) == 2:
            return self.source(*args)
        if len(args) == 3:
            return self.transform(*args)
        raise TypeError(
            f"{type(self).__name__} called with {len(args)} args "
            f"(expected 2 for source or 3 for transform)"
        )

    def source(self, arg: str, ctx: Context) -> Any:
        """Produce a value from *arg*.

        Override for resolvers that appear first in a pipeline
        (e.g. ``load``, ``env``, ``ref``).
        """
        raise NotImplementedError(
            f"{type(self).__name__} cannot be used as a source"
        )

    def transform(self, data: Any, arg: str, ctx: Context) -> Any:
        """Transform piped *data*.

        Override for resolvers that receive input from a previous
        step (e.g. ``sort``, ``filter``, ``limit``).
        """
        raise NotImplementedError(
            f"{type(self).__name__} cannot be used as a transform"
        )
