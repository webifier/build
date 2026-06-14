from __future__ import annotations

import subprocess
from typing import Any

_NO_DEFAULT = object()


def resolve_path(
    context: Any,
    path: str,
    *,
    separator: str = ".",
    default: Any = _NO_DEFAULT,
) -> Any:
    """Walk a *separator*-delimited *path* on *context*.

    At each segment the function tries, in order:

    1. ``__getitem__``  (dicts, lists-by-index, etc.)
    2. ``getattr``      (objects with attributes)

    Args:
        context:   The root object to traverse.
        path:      Separator-delimited path, e.g. ``"nav.brand.text"``.
        separator: Delimiter between segments (default ``"."``).
        default:   Value to return when the path cannot be resolved.
                   If omitted, a :class:`KeyError` is raised.

    Returns:
        The value found at *path*, or *default*.

    Raises:
        KeyError: If the path cannot be resolved and no *default* is given.
    """
    node = context
    for part in path.split(separator):
        # try __getitem__ first (dicts, sequences, …)
        try:
            node = node[part]
            continue
        except (KeyError, TypeError, IndexError):
            pass

        # try attribute access (objects, namedtuples, …)
        try:
            node = getattr(node, part)
            continue
        except AttributeError:
            pass

        # neither worked
        if default is not _NO_DEFAULT:
            return default
        raise KeyError(
            f"Cannot resolve segment {part!r} in path {path!r}"
        )

    return node


def place_at_path(
    root: dict,
    path: str,
    value: Any,
    *,
    separator: str = ".",
    factory: type = dict,
) -> None:
    """Place *value* at a *separator*-delimited *path* in *root*.

    Intermediate containers are created with *factory* (default ``dict``).
    If the final node and *value* are both dicts, they are merged
    (value wins on conflict).  Otherwise *value* replaces.

    Args:
        root:      Mutable mapping to write into.
        path:      Separator-delimited target, e.g. ``"nav.links"``.
        value:     The value to store.
        separator: Delimiter between segments (default ``"."``).
        factory:   Callable that creates intermediate containers.
    """
    parts = path.split(separator)
    current = root
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = factory()
        current = current[part]

    final = parts[-1]
    if (
        final in current
        and isinstance(current[final], dict)
        and isinstance(value, dict)
    ):
        current[final].update(value)
    else:
        current[final] = value


def parse_step(step: str) -> tuple[str, str]:
    """Split a resolver step ``name:arg`` into ``(name, arg)``."""
    if ":" in step:
        name, arg = step.split(":", 1)
        return name.strip(), arg.strip()
    return step.strip(), ""


def git_timestamp(item: dict, key: str) -> float:
    """Return a git timestamp for *item* (must have ``_source``)."""
    if not isinstance(item, dict) or "_source" not in item:
        return 0
    src = item["_source"]
    fmt = (
        "--format=%at"
        if key in ("git:authored", "git:created")
        else "--format=%ct"
    )
    try:
        cmd = ["git", "log", "-1", fmt, "--", src]
        if key == "git:created":
            cmd = [
                "git", "log", "--follow", "--diff-filter=A", fmt, "--", src,
            ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return float(r.stdout.strip() or 0)
    except Exception:
        return 0
