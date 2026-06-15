from __future__ import annotations

import os
import re
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

# Matches optional type prefix (md=, index=, pdf=, notebook=) followed by a URL
HREF_REGEX = re.compile(
    r"((?P<type>(index|pdf|md|notebook))=)?(?P<url>((http|ftp)s?://)?(-\.)?[\w\d\S]+)"
)


def process_html(
    builder,
    raw_html: str,
    assets_src_dir=None,
    assets_target_dir=None,
    search_links: bool = False,
) -> str:
    """Post-process HTML — resolve anchors and local asset paths."""
    assets_target_dir = assets_target_dir if assets_target_dir is not None else builder.assets_dir
    soup = BeautifulSoup(raw_html, features="html.parser")

    # Resolve anchor hrefs (md=, index=, pdf=, notebook= prefixes)
    for anchor in soup.find_all("a"):
        _process_html_anchor(
            builder,
            soup,
            anchor,
            assets_src_dir=assets_src_dir,
            assets_target_dir=assets_target_dir,
            search_links=search_links,
        )

    # Resolve src attributes on media tags
    for tag in ["img", "audio", "embed", "iframe", "script", "source", "track", "video"]:
        for src_tag in soup.find_all(tag, src=True):
            src = src_tag["src"]
            local_src = src
            if "://" not in src and not src.startswith("data:"):
                local_src = unquote(urlsplit(src).path)
            try:
                new_src = builder.files.copy_file(
                    local_src,
                    local_src,
                    src_dir=assets_src_dir,
                    target_dir=assets_target_dir,
                )
            except FileNotFoundError:
                fallback_src = os.path.join("files", local_src)
                if not assets_src_dir or local_src.startswith("files/") or not os.path.isfile(
                    os.path.join(assets_src_dir, fallback_src)
                ):
                    raise
                new_src = builder.files.copy_file(
                    fallback_src,
                    fallback_src,
                    src_dir=assets_src_dir,
                    target_dir=assets_target_dir,
                )
            if new_src:
                src_tag["src"] = new_src

    return str(soup)


def _process_html_anchor(
    builder,
    soup,
    anchor,
    assets_src_dir=None,
    assets_target_dir=None,
    search_links=False,
):
    """Process a single ``<a>`` tag — resolve md=/index=/pdf= link prefixes."""
    if "href" not in anchor.attrs or not anchor["href"]:
        return

    href = anchor["href"]
    match = re.match(HREF_REGEX, href)
    if not match:
        return

    match_dict = match.groupdict()
    link_type = match_dict.get("type")
    url = match_dict.get("url", "")

    if not link_type:
        # No prefix — leave as-is (normal URL or anchor)
        return

    link = {"text": anchor.text or ""}
    for key in anchor.attrs:
        if key not in ("href", "class"):
            link[key] = anchor[key]

    if link_type in ("md", "notebook"):
        # Build a content sub-page
        link["src"] = url
        from .base import NodeContext

        ctx = NodeContext(
            assets_src_dir=assets_src_dir,
            assets_target_dir=assets_target_dir,
            search_links=search_links,
        )
        link = builder._process_content_link(link, ctx, kind=link_type)
        anchor["href"] = link.get("href", "#")

    elif link_type == "index":
        # Build a sub-page from an index file
        link["src"] = url
        from .base import NodeContext

        ctx = NodeContext(
            assets_src_dir=assets_src_dir,
            assets_target_dir=assets_target_dir,
            search_links=search_links,
        )
        link = builder._process_index_link(link, ctx)
        anchor["href"] = link.get("href", "#")

    elif link_type == "pdf":
        new_path = builder.files.copy_file(
            url,
            url,
            target_dir="assets",
        )
        anchor["href"] = new_path if new_path else url

    # Add tooltip for description
    if "description" in link:
        anchor["data-bs-toggle"] = "tooltip"
        anchor["data-bs-html"] = "true"
        anchor["title"] = link["description"]

    # Add icon if specified
    if "icon" in link:
        text = anchor.text
        anchor.clear()
        icon_tag = soup.new_tag("i")
        icon_tag["aria-hidden"] = "true"
        icon_tag["class"] = link["icon"]
        anchor.append(icon_tag)
        anchor.append(f" {text}")
        if "icon" in anchor.attrs:
            del anchor["icon"]
