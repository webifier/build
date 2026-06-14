from __future__ import annotations

import datetime
import glob as _glob
import os
from typing import Any

from .base import Context, Resolver
from .utils import git_timestamp, resolve_path

# ── Source resolvers ──────────────────────────────────────────────────────


class Load(Resolver):
    """Load a YAML or text file: ``${load:path/to/file.yml}``"""

    def source(self, arg: str, ctx: Context) -> Any:
        import yaml

        if arg.endswith((".yml", ".yaml")):
            with open(arg) as f:
                return yaml.safe_load(f) or {}
        with open(arg) as f:
            return f.read()


class Glob(Resolver):
    """Glob for files and load each: ``${glob:posts/*.yml}``"""

    def source(self, arg: str, ctx: Context) -> list:
        import yaml

        results: list[Any] = []
        for path in sorted(_glob.glob(arg, recursive=True)):
            if path.endswith((".yml", ".yaml")):
                with open(path) as f:
                    item = yaml.safe_load(f) or {}
                if isinstance(item, dict):
                    item["_source"] = path
                results.append(item)
            else:
                with open(path) as f:
                    results.append({"content": f.read(), "_source": path})
        return results


class Env(Resolver):
    """Read an environment variable: ``${env:API_KEY}``"""

    def source(self, arg: str, ctx: Context) -> str:
        return os.environ.get(arg, "")


class Ref(Resolver):
    """Reference another value in the document.

    ``${ref:.title}``         — sibling key
    ``${ref:nav.brand.text}`` — absolute dotted path from root
    """

    def source(self, arg: str, ctx: Context) -> Any:
        if arg.startswith("."):
            key = arg.lstrip(".")
            if key in ctx.current:
                return ctx.current[key]
            return resolve_path(ctx.root, key, default=None)
        return resolve_path(ctx.root, arg, default=None)


class Now(Resolver):
    """Current date/time: ``${now:%Y-%m-%d}``"""

    def source(self, arg: str, ctx: Context) -> str:
        return datetime.datetime.now().strftime(arg or "%Y-%m-%d")


class Baseurl(Resolver):
    """Site base URL: ``${baseurl:path/to/page}``"""

    def source(self, arg: str, ctx: Context) -> str:
        base = resolve_path(ctx.root, "config.baseurl", default="")
        if arg:
            return f"/{base}/{arg}".replace("//", "/") if base else f"/{arg}"
        return f"/{base}" if base else ""


class Asset(Resolver):
    """Asset path under baseurl: ``${asset:css/main.css}``"""

    def source(self, arg: str, ctx: Context) -> str:
        base = resolve_path(ctx.root, "config.baseurl", default="")
        return (
            f"/{base}/assets/{arg}".replace("//", "/")
            if base
            else f"/assets/{arg}"
        )


class Md(Resolver):
    """Read a markdown file's raw content: ``${md:path/to/file.md}``"""

    def source(self, arg: str, ctx: Context) -> str:
        if os.path.isfile(arg):
            with open(arg) as f:
                return f.read()
        return arg


# ── Transform resolvers ──────────────────────────────────────────────────


class Sort(Resolver):
    """Sort a list: ``${… | sort:name}`` or ``${… | sort:-date}``"""

    def transform(self, data: Any, arg: str, ctx: Context) -> list:
        if not isinstance(data, list):
            return data
        desc = arg.startswith("-")
        key = arg.lstrip("-") or "name"
        return sorted(data, key=self._key_fn(key), reverse=desc)

    @staticmethod
    def _key_fn(key: str):
        if key == "name":
            return lambda x: (
                x.get("_source", "") if isinstance(x, dict) else str(x)
            )
        if key == "modified":
            return lambda x: (
                os.path.getmtime(x["_source"])
                if isinstance(x, dict) and "_source" in x
                else 0
            )
        if key.startswith("git"):
            return lambda x: git_timestamp(x, key)
        return lambda x: (
            x.get(key, "") if isinstance(x, dict) else str(x)
        )


class Reverse(Resolver):
    """Reverse a list: ``${… | reverse}``"""

    def transform(self, data: Any, arg: str, ctx: Context) -> Any:
        return list(reversed(data)) if isinstance(data, list) else data


class Limit(Resolver):
    """Take first N items: ``${… | limit:5}``"""

    def transform(self, data: Any, arg: str, ctx: Context) -> Any:
        if isinstance(data, list) and arg.isdigit():
            return data[: int(arg)]
        return data


class Offset(Resolver):
    """Skip first N items: ``${… | offset:2}``"""

    def transform(self, data: Any, arg: str, ctx: Context) -> Any:
        if isinstance(data, list) and arg.isdigit():
            return data[int(arg) :]
        return data


class Filter(Resolver):
    """Filter items: ``${… | filter:key=value}`` or ``${… | filter:key}``"""

    def transform(self, data: Any, arg: str, ctx: Context) -> Any:
        if not isinstance(data, list):
            return data
        if "=" in arg:
            k, v = arg.split("=", 1)
            return [
                i
                for i in data
                if isinstance(i, dict) and str(i.get(k)) == v
            ]
        return [i for i in data if isinstance(i, dict) and i.get(arg)]


class Exclude(Resolver):
    """Exclude items: ``${… | exclude:key=value}``"""

    def transform(self, data: Any, arg: str, ctx: Context) -> Any:
        if not isinstance(data, list):
            return data
        if "=" in arg:
            k, v = arg.split("=", 1)
            return [
                i
                for i in data
                if not (isinstance(i, dict) and str(i.get(k)) == v)
            ]
        return [
            i for i in data if not (isinstance(i, dict) and i.get(arg))
        ]


class Flatten(Resolver):
    """Flatten nested lists: ``${… | flatten}``"""

    def transform(self, data: Any, arg: str, ctx: Context) -> Any:
        if not isinstance(data, list):
            return data
        out: list[Any] = []
        for item in data:
            if isinstance(item, list):
                out.extend(item)
            else:
                out.append(item)
        return out


class Unique(Resolver):
    """De-duplicate: ``${… | unique:key}`` or ``${… | unique}``"""

    def transform(self, data: Any, arg: str, ctx: Context) -> Any:
        if not isinstance(data, list):
            return data
        if arg:
            seen: set[Any] = set()
            result: list[Any] = []
            for item in data:
                val = item.get(arg) if isinstance(item, dict) else item
                if val not in seen:
                    seen.add(val)
                    result.append(item)
            return result
        result = []
        for item in data:
            if item not in result:
                result.append(item)
        return result


class Map(Resolver):
    """Extract a key from each item: ``${… | map:title}``"""

    def transform(self, data: Any, arg: str, ctx: Context) -> Any:
        if not isinstance(data, list) or not arg:
            return data
        return [i.get(arg) if isinstance(i, dict) else i for i in data]


class Count(Resolver):
    """Count items: ``${… | count}``"""

    def transform(self, data: Any, arg: str, ctx: Context) -> int:
        return len(data) if isinstance(data, (list, dict)) else 0


class Group(Resolver):
    """Group by key: ``${… | group:category}``"""

    def transform(self, data: Any, arg: str, ctx: Context) -> Any:
        if not isinstance(data, list) or not arg:
            return data
        groups: dict[str, list] = {}
        for item in data:
            k = (
                str(item.get(arg, "other"))
                if isinstance(item, dict)
                else "other"
            )
            groups.setdefault(k, []).append(item)
        return groups


