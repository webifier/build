from __future__ import annotations

import argparse
from dataclasses import MISSING, dataclass, field, fields

from webifier import __version__
from webifier.core.builder import Builder


@dataclass
class WebifierArgs:
    """Command-line arguments for the Webifier build tool."""

    base_url: str = field(
        default="",
        metadata={"flag": "--baseurl", "help": "Baseurl of deploying site"},
    )
    repo_full_name: str | None = field(
        default=None,
        metadata={"flag": "--repo-full-name", "help": "user/repo_name"},
    )
    index: str = field(
        default="index.yml",
        metadata={"flag": "--index", "help": "initial page (default: index.yml)"},
    )
    output: str = field(
        default="webified",
        metadata={
            "flag": "--output",
            "help": 'build target directory (default: "webified")',
        },
    )
    templates_dir: str = field(
        default=".",
        metadata={
            "flag": "--templates-dir",
            "help": 'templates base directory (default: ".")',
        },
    )

    @classmethod
    def make_parser(cls) -> argparse.ArgumentParser:
        """Generate an ``ArgumentParser`` from the dataclass fields."""
        parser = argparse.ArgumentParser(
            description=(
                f"Webify ({__version__}) — build a static website from YAML and Markdown."
            )
        )
        for f in fields(cls):
            meta = f.metadata
            flag = meta.get("flag", f"--{f.name.replace('_', '-')}")
            kwargs: dict = {"dest": f.name, "help": meta.get("help", "")}
            if f.default is not MISSING:
                kwargs["default"] = f.default
            parser.add_argument(flag, **kwargs)
        return parser

    @classmethod
    def from_argv(cls, argv: list[str] | None = None) -> WebifierArgs:
        """Parse *argv* (or ``sys.argv[1:]``) and return a populated instance."""
        parser = cls.make_parser()
        ns = parser.parse_args(argv)
        return cls(**vars(ns))


def main():
    """Entry point for the ``webify`` console command."""
    args = WebifierArgs.from_argv()

    print(f"webifier: {__version__}, baseurl: {args.base_url}")

    builder = Builder(
        base_url=args.base_url,
        repo_full_name=args.repo_full_name,
        output_dir=args.output,
        templates_dir=args.templates_dir,
    )
    builder.build(index_file=args.index)
