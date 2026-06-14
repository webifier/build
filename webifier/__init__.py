from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("webifier")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

from webifier.core import register_renderer  # noqa: E402
from webifier.interface.resolvers import (  # noqa: E402
    register_resolver,
    register_source,
    register_transform,
)

__all__ = [
    "__version__",
    "register_resolver",
    "register_renderer",
    "register_source",
    "register_transform",
]
