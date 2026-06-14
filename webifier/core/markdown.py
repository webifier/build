from __future__ import annotations

import typing as th

import markdown

from .html import process_html as html_processor


def build_markdown(
    raw: str,
    builder,
    assets_src_dir=None,
    assets_target_dir=None,
    extensions: th.Iterable[str] | None = None,
    process_html: bool = True,
    search_links: bool = False,
) -> str:
    """Convert raw markdown to HTML, copying local assets when needed."""
    assets_target_dir = builder.assets_dir if assets_target_dir is None else assets_target_dir
    body = markdown.markdown(
        raw, extensions=extensions if extensions else builder.markdown_extensions
    )
    if process_html:
        return html_processor(
            builder,
            body,
            assets_src_dir=assets_src_dir,
            assets_target_dir=assets_target_dir,
            search_links=search_links,
        )
    return body
