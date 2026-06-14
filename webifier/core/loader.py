from __future__ import annotations

import collections
import copy
import os
from typing import Any

from webifier.interface.io import read_file, read_yaml
from webifier.interface.resolvers import expand
from webifier.interface.resolvers.utils import place_at_path

# ---------------------------------------------------------------------------
# Phase 2: patch resolution
# ---------------------------------------------------------------------------

_PATCH_KEY = "patch"

# Built-in !modifiers.  ``auto`` is the default (extension-based dispatch).
_BUILTIN_MODIFIERS = frozenset({"auto", "yaml", "text", "value"})

# Extensible format registry — maps file extensions to loader functions.
# Each loader takes a file path string and returns loaded data (dict, str, etc.).
_FORMAT_REGISTRY: dict[str, Any] = {}


def register_format(extension: str, loader_fn) -> None:
    """Register a loader for a file extension.

    Parameters
    ----------
    extension : str
        File extension **with** the leading dot, e.g. ``".yml"``, ``".md"``.
    loader_fn : callable
        ``(path: str) -> Any``.  Receives the file path, returns loaded data.
    """
    _FORMAT_REGISTRY[extension.lower()] = loader_fn


def _register_builtin_formats() -> None:
    """Seed the format registry with built-in loaders."""
    register_format(".yml", read_yaml)
    register_format(".yaml", read_yaml)
    register_format(".md", read_file)
    register_format(".markdown", read_file)
    register_format(".txt", read_file)
    register_format(".html", read_file)
    register_format(".css", read_file)
    register_format(".js", read_file)
    register_format(".json", read_file)


# Initialise on import
_register_builtin_formats()


# --- Key parsing -----------------------------------------------------------

def _is_patch_key(key: str) -> bool:
    """Return True if *key* is a ``patch`` directive.

    Matches: ``patch``, ``patch@loc``, ``patch!mod``, ``patch@loc!mod``.
    """
    if not isinstance(key, str):
        return False
    if key == _PATCH_KEY:
        return True
    if key.startswith(_PATCH_KEY):
        next_char = key[len(_PATCH_KEY)]
        return next_char in ("@", "!")
    return False


def _parse_patch_key(key: str) -> tuple[str | None, str | None]:
    """Parse a patch key into *(location, modifier)*.

    Grammar::

        patch[@LOCATION][!MODIFIER]

    Returns
    -------
    (location, modifier) : tuple[str | None, str | None]
        *location* is a dotted path (``None`` → ``_here_``).
        *modifier* is e.g. ``"value"``, ``"yaml"`` (``None`` → ``auto``).

    Examples
    --------
    >>> _parse_patch_key("patch")
    (None, None)
    >>> _parse_patch_key("patch@nav")
    ('nav', None)
    >>> _parse_patch_key("patch@nav.links")
    ('nav.links', None)
    >>> _parse_patch_key("patch!value")
    (None, 'value')
    >>> _parse_patch_key("patch@title!value")
    ('title', 'value')
    >>> _parse_patch_key("patch@a.b!yaml")
    ('a.b', 'yaml')
    """
    rest = key[len(_PATCH_KEY):]
    if not rest:
        return None, None

    location = None
    modifier = None

    # Split off !modifier (must come after @location if both present)
    if "!" in rest:
        rest, modifier = rest.rsplit("!", 1)
        if modifier not in _BUILTIN_MODIFIERS:
            raise ValueError(
                f"Unknown patch modifier '!{modifier}' in key '{key}'. "
                f"Valid modifiers: {', '.join(sorted(_BUILTIN_MODIFIERS))}"
            )
        if modifier == "auto":
            modifier = None  # explicit !auto is same as omitting

    # What remains after stripping !modifier is @location
    if rest:
        if not rest.startswith("@"):
            raise ValueError(
                f"Invalid patch key '{key}'. Expected '@' before location, got '{rest}'."
            )
        location = rest[1:]  # strip the '@'
        if not location:
            raise ValueError(f"Empty @location in patch key '{key}'.")

    return location, modifier


# --- Patch resolution -------------------------------------------------------

def resolve_patches(data: Any) -> Any:
    """Recursively resolve ``patch`` directives in a data tree.

    Directives are processed in YAML insertion order; later patches
    merge on top of earlier ones.  Explicit (non-patch) keys in the
    parent always win over patched values.

    Examples::

        patch: config.yml              # merge config dict here
        patch@nav: nav.yml             # merge into "nav" key
        patch@content!text: data.yml   # read as text, set "content"
        patch@title!value: Hello       # literal value under "title"
    """
    if not isinstance(data, dict):
        return data

    # Separate patch keys from regular keys
    patch_keys = [k for k in data if _is_patch_key(k)]
    regular_keys = [k for k in data if not _is_patch_key(k)]

    # Recurse into regular children first
    result = collections.OrderedDict()
    for key in regular_keys:
        result[key] = resolve_patches(data[key])

    # Apply patches in order (insertion order preserved)
    if patch_keys:
        merged = collections.OrderedDict()

        for pkey in patch_keys:
            location, modifier = _parse_patch_key(pkey)
            patch_val = data[pkey]

            # !value treats the entire value literally — never unpack lists
            # as multiple sources.  Without !value, lists are iterated as
            # multiple patch sources merged in order.
            sources = [patch_val] if modifier == "value" or not isinstance(patch_val, list) else patch_val

            for source in sources:
                loaded = _load_patch(source, modifier)

                if location is not None:
                    # @location specified — place content at dotted path
                    if isinstance(loaded, dict):
                        loaded = resolve_patches(loaded)
                    place_at_path(merged, location, loaded)
                else:
                    # No @location — merge here (original behaviour)
                    if isinstance(loaded, dict):
                        loaded = resolve_patches(loaded)
                        for k, v in loaded.items():
                            merged[k] = v
                    elif not result and len(patch_keys) == 1:
                        # Bare patch with scalar as only content → return
                        # the scalar directly.
                        return loaded
                    else:
                        merged["content"] = loaded

        # Explicit keys win over patched values
        for k, v in result.items():
            merged[k] = v
        result = merged

    return result


def _load_patch(source: Any, modifier: str | None = None) -> Any:
    """Load a patch source, respecting the ``!modifier``.

    Modifiers
    ---------
    ``None`` (auto)
        Use the format registry to dispatch by file extension.
        Unknown extensions fall back to plain text.
    ``"yaml"``
        Force-load as YAML.
    ``"text"``
        Force-load as plain text.
    ``"value"``
        Use the value literally — **no** file loading.
    """
    # !value — use as-is, never load from disk
    if modifier == "value":
        return source

    # Inline dicts are always used directly (no file loading)
    if isinstance(source, dict):
        return source

    if isinstance(source, str):
        if modifier == "yaml":
            return read_yaml(source)
        if modifier == "text":
            return read_file(source)
        # Auto-detect via format registry
        _, ext = os.path.splitext(source)
        loader_fn = _FORMAT_REGISTRY.get(ext.lower())
        if loader_fn is not None:
            return loader_fn(source)
        # Fallback: read as text
        return read_file(source)

    return source


# ---------------------------------------------------------------------------
# Phase 3: defaults application
# ---------------------------------------------------------------------------


def apply_defaults(data: Any) -> Any:
    """Apply ``defaults`` directives to sibling dicts.

    ``defaults`` provides default values for all sibling dict entries
    that don't have those keys set. This replaces the old ``sub-*`` mechanism.
    """
    if not isinstance(data, dict):
        return data

    defaults = data.pop("defaults", None)

    result = collections.OrderedDict()
    for key, value in data.items():
        if isinstance(value, dict) and defaults:
            # Apply defaults — existing keys win
            merged = collections.OrderedDict()
            for dk, dv in defaults.items():
                merged[dk] = copy.deepcopy(dv)
            merged.update(value)
            result[key] = apply_defaults(merged)
        else:
            result[key] = apply_defaults(value)

    return result


# ---------------------------------------------------------------------------
# Full pipeline: load → patch → defaults → interpolate
# ---------------------------------------------------------------------------


def load_and_resolve(path: str) -> dict:
    """Load a YAML file and run it through all pre-render phases.

    Returns the fully resolved data dict ready for rendering.
    """
    data = read_yaml(path)
    data = resolve_patches(data)
    data = apply_defaults(data)
    data = expand(data)
    return data
