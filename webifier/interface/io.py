from __future__ import annotations

import collections
import os
import pathlib
import shutil
from typing import Any

import yaml

# ── YAML helpers — preserve insertion order ───────────────────────────────

_mapping_tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG


def _dict_representer(dumper: yaml.Dumper, data: dict) -> yaml.Node:
    return dumper.represent_mapping(_mapping_tag, data.items())


def _dict_constructor(loader: yaml.Loader, node: yaml.Node) -> dict:
    return collections.OrderedDict(loader.construct_pairs(node))


yaml.add_representer(collections.OrderedDict, _dict_representer)
yaml.add_constructor(_mapping_tag, _dict_constructor)


# ── Standalone functions ──────────────────────────────────────────────────


def read_yaml(path: str) -> Any:
    """Load a YAML file, preserving key order."""
    with open(path) as fh:
        return yaml.full_load(fh)


def read_file(path: str) -> str:
    """Read a text file and return its content."""
    with open(path) as fh:
        return fh.read()


def strip_suffixes(text: str, suffixes: str | list[str]) -> str:
    """Strip one or more *suffixes* from the end of *text*.

    >>> strip_suffixes("page.md", ".md")
    'page'
    >>> strip_suffixes("page.nb.ipynb", [".ipynb", ".nb"])
    'page'
    """
    if isinstance(suffixes, list):
        for s in suffixes:
            text = strip_suffixes(text, s)
        return text
    return text[: -len(suffixes)] if text.endswith(suffixes) else text


def prepend_baseurl(
    url: str,
    baseurl: str | None = None,
    *,
    ensure_html: bool = True,
) -> str:
    """Prepend *baseurl* to *url*, optionally ensuring an ``.html`` suffix.

    >>> prepend_baseurl("about", baseurl="site")
    '/site/about.html'
    >>> prepend_baseurl("about", baseurl="")
    '/about.html'
    >>> prepend_baseurl("logo.png", baseurl="site", ensure_html=False)
    '/site/logo.png'
    """
    if baseurl is None:
        result = url
    else:
        clean_baseurl = baseurl.strip("/")
        prefix = f"/{clean_baseurl}" if clean_baseurl else ""
        result = f"{prefix}/{url.lstrip('/')}"
    if ensure_html:
        if not result.endswith(".html"):
            result = f"{result}.html"
        if baseurl is not None:
            result = strip_suffixes(result, "index.html")
    return result


# ── FileManager ───────────────────────────────────────────────────────────


class FileManager:
    """Handles file copying and directory merging for a build.

    Parameters
    ----------
    output_dir:
        Root directory for all output.
    assets_dir:
        Sub-directory (relative to *output_dir*) for copied assets.
    baseurl:
        URL prefix prepended to generated paths.
    """

    def __init__(
        self,
        output_dir: str = "webified",
        assets_dir: str = "assets",
        baseurl: str = "",
    ) -> None:
        self.output_dir = output_dir
        self.assets_dir = assets_dir
        self.baseurl = baseurl

    # -- single file -------------------------------------------------------

    def copy_file(
        self,
        src: str,
        target: str,
        *,
        src_dir: str | None = None,
        target_dir: str | None = None,
    ) -> str | None:
        """Copy a local file into the output tree, returning its URL path.

        Returns ``None`` for remote URLs or data-URIs (nothing to copy).
        """
        if "://" in src or src.startswith("data:"):
            return None

        target_dir = target_dir or self.assets_dir
        full_src = os.path.join(src_dir, src) if src_dir else src

        if not os.path.isfile(full_src):
            raise FileNotFoundError(f"Source file does not exist: {full_src}")

        # Compute destination directory from the target's parent segments
        parent = str(pathlib.Path(target).parent)
        parent = "" if parent == "." else parent

        dest_dir = os.path.join(self.output_dir, target_dir, parent)
        os.makedirs(dest_dir, exist_ok=True)

        dest_path = os.path.join(target_dir, target)
        shutil.copy2(full_src, os.path.join(self.output_dir, dest_path))

        return prepend_baseurl(dest_path, self.baseurl, ensure_html=False)

    # -- directory merge ---------------------------------------------------

    def merge_dirs(
        self,
        src_dir: str,
        target_dir: str,
        *,
        allow_list: list[str] | None = None,
        overwrite: bool = False,
    ) -> None:
        """Recursively copy *src_dir* into *target_dir*.

        When *allow_list* is given, only top-level entries whose name
        appears in the list are copied (together with their subtrees).
        """
        if os.path.abspath(src_dir) == os.path.abspath(target_dir):
            return

        for dirpath, _dirs, files in os.walk(src_dir):
            rel = os.path.relpath(dirpath, src_dir)
            # Check allow_list for top-level entries
            if allow_list and rel != ".":
                top_entry = rel.split(os.sep)[0]
                if top_entry not in allow_list:
                    continue

            dst = os.path.join(target_dir, rel) if rel != "." else target_dir
            os.makedirs(dst, exist_ok=True)

            for fname in files:
                if allow_list and rel == "." and fname not in allow_list:
                    continue
                dst_file = os.path.join(dst, fname)
                if overwrite or not os.path.exists(dst_file):
                    shutil.copy(os.path.join(dirpath, fname), dst)

    # -- convenience -------------------------------------------------------

    def write(self, path: str, content: str) -> None:
        """Write *content* to *path* under the output directory."""
        full = os.path.join(self.output_dir, path)
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w") as f:
            f.write(content)


__all__ = [
    "FileManager",
    "prepend_baseurl",
    "read_file",
    "read_yaml",
    "strip_suffixes",
]
