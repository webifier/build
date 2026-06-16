from __future__ import annotations

import copy
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import jinja2

from webifier.interface.io import FileManager, prepend_baseurl, strip_suffixes

from .base import GenericTemplateRenderer, NodeContext, resolve_renderer
from .extensions import ExtensionManager
from .frontmatter import split_yaml_front_matter
from .loader import apply_defaults, load_and_resolve, read_yaml, resolve_patches
from .markdown import build_markdown


@dataclass
class Builder:
    """Orchestrates the site build.

    Thin dispatch — loads data, resolves renderers, and delegates all
    rendering to RendererModule subclasses.
    """

    base_url: str = ""
    repo_full_name: str | None = None
    output_dir: str = "webified"
    assets_dir: str = "assets"
    templates_dir: str = "."
    markdown_extensions: tuple[str, ...] = (
        "md_in_html",
        "codehilite",
        "fenced_code",
        "tables",
        "attr_list",
        "footnotes",
        "def_list",
    )

    # Runtime state
    config: dict = field(default_factory=dict)
    config_defaults: dict = field(default_factory=dict)
    search_entries: dict = field(default_factory=dict)
    processed_pages: set = field(default_factory=set)
    root_data: dict | None = field(default=None, repr=False)
    extensions_configured: bool = field(default=False, init=False)
    content_renderers: dict[str, Callable] = field(default_factory=dict)

    # File manager
    files: FileManager = field(default=None, init=False, repr=False)

    # Jinja2 environment
    jinja_env: jinja2.Environment = field(default=None, init=False, repr=False)
    extensions: ExtensionManager = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self.files = FileManager(
            output_dir=self.output_dir,
            assets_dir=self.assets_dir,
            baseurl=self.base_url,
        )

        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader([self.templates_dir]),
            autoescape=False,
            extensions=["jinja2.ext.loopcontrols"],
        )
        self.extensions = ExtensionManager(self)

    # ------------------------------------------------------------------
    # Extension runup
    # ------------------------------------------------------------------

    def _preload_config(self, index_file: str) -> dict:
        """Load enough of the root page to configure extensions before interpolation."""
        if not index_file.endswith((".yml", ".yaml")):
            index_file = f"{index_file}.yml"
        data = read_yaml(index_file)
        data = resolve_patches(data)
        data = apply_defaults(data)
        config: dict[str, Any] = {}
        if isinstance(data, dict) and isinstance(data.get("config"), dict):
            config = dict(data["config"])
        if isinstance(data, dict) and isinstance(data.get("webifier"), dict):
            config.setdefault("webifier", data["webifier"])
        return config

    def configure_extensions(self, config: dict) -> None:
        """Run the extension setup phase before rendering begins."""
        if self.extensions_configured:
            return
        self.extensions.configure(config)
        self.extensions_configured = True

    def _ensure_extensions_configured(self, index_file: str) -> None:
        if not self.extensions_configured:
            self.configure_extensions(self._preload_config(index_file))

    def render_extension_area(self, area: str, **kwargs) -> str:
        """Render HTML fragments contributed by enabled extensions."""
        kwargs.setdefault("config", self.config)
        return self.extensions.render_area(area, **kwargs)

    def page_config(self, data: dict | None = None) -> dict:
        """Return global config merged with page-local config."""
        config = copy.deepcopy(self.config)
        if isinstance(data, dict):
            page_configs = []
            if isinstance(data.get("config"), dict):
                page_configs.append(data["config"])
            metadata = data.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("config"), dict):
                page_configs.append(metadata["config"])
            for page_config in page_configs:
                self.extensions.configure_page_extensions(page_config)
                for key, value, reset in self.extensions.page_config_overlays(page_config):
                    if reset:
                        config[key] = copy.deepcopy(value)
                    else:
                        config[key] = _deep_merge(config.get(key, {}), value)
                config = _deep_merge(config, page_config)
        return config

    def page_navigation(self, config: dict | None = None, data: dict | None = None, ctx=None) -> dict:
        """Return previous/home/next links for a page from config.page_navigation."""
        nav_config = (config or {}).get("page_navigation")
        if not isinstance(nav_config, dict):
            return {}

        def link_from(value: Any, fallback_title: str = "") -> dict[str, str] | None:
            if value is False or value is None:
                return None
            if isinstance(value, str):
                return {"title": fallback_title or value, "href": value}
            if not isinstance(value, dict):
                return None
            href = value.get("href") or value.get("link")
            src = value.get("src", "")
            if not href and src:
                href = prepend_baseurl(strip_suffixes(src, suffixes), self.base_url)
            if not href:
                return None
            return {
                "title": value.get("title") or value.get("text") or fallback_title or href,
                "href": href,
            }

        entries = []
        suffixes = self._content_suffixes() + [".yml", ".yaml"]

        def collect(items):
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                child_items = item.get("items")
                if isinstance(child_items, list):
                    collect(child_items)
                elif item.get("href") or item.get("link") or item.get("src"):
                    entry = link_from(item)
                    if entry:
                        entry["src"] = item.get("src", "")
                        entries.append(entry)

        collect(nav_config.get("items"))

        current_values = []
        if isinstance(data, dict):
            current_values.extend(
                value
                for value in (
                    data.get("page_url"),
                    data.get("source_path"),
                    data.get("_source_path"),
                )
                if value
            )
        if not current_values and ctx is not None and getattr(ctx, "page_url", None):
            current_values.append(ctx.page_url)

        normalized_current = {_normalize_page_nav_value(value, suffixes) for value in current_values}
        active_index = None
        for i, entry in enumerate(entries):
            normalized_entry = {
                _normalize_page_nav_value(value, suffixes)
                for value in (entry.get("href"), entry.get("src"))
                if value
            }
            if normalized_current & normalized_entry:
                active_index = i
                break

        result = {}
        home = link_from(nav_config.get("home"), "Guide")
        if home:
            result["home"] = home
        if active_index is not None:
            if active_index > 0:
                result["previous"] = entries[active_index - 1]
            if active_index < len(entries) - 1:
                result["next"] = entries[active_index + 1]

        for slot in ("previous", "home", "next"):
            if slot not in nav_config:
                continue
            if nav_config[slot] is False:
                result.pop(slot, None)
                continue
            override = link_from(nav_config[slot], slot.title())
            if override:
                result[slot] = override
        return result

    def _copy_extension_assets(self) -> None:
        for mount in self.extensions.asset_mounts:
            if os.path.isdir(mount.source):
                self.files.merge_dirs(mount.source, os.path.join(self.output_dir, mount.target), overwrite=True)

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------

    def process_node(self, data: Any, ctx: NodeContext) -> Any:
        """Universal dispatch — the core loop.

        Determines the renderer for *data* based on its type and any
        ``kind`` / ``template`` directive, then delegates to the renderer's
        ``process()`` and ``render()`` methods.
        """
        if isinstance(data, str):
            kind = self.config_defaults.get("markdown", "markdown")
            renderer = resolve_renderer(kind, jinja_env=self.jinja_env)
            return renderer.render({"content": data}, ctx, self)

        if isinstance(data, list):
            kind = self.config_defaults.get("links", "links")
            renderer = resolve_renderer(kind, jinja_env=self.jinja_env)
            processed_items = []
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    processed_items.append(self._process_link(item, ctx.child(str(i))))
                else:
                    processed_items.append(item)
            return renderer.render({"items": processed_items}, ctx, self)

        if isinstance(data, dict):
            data = copy.deepcopy(data)
            if ctx.depth == 0:
                data = self.extensions.consume_page_keys(data, ctx=ctx, config=self.page_config(data))

            # template: path (inline override) takes precedence, but only
            # at the page level (depth 0). At section level, `template` is
            # passed through to the section renderer, which uses it as an
            # inner content template while still providing the section
            # wrapper (label, background, etc.).
            if "template" in data and ctx.depth == 0:
                tmpl_path = data.pop("template")
                renderer = GenericTemplateRenderer(template=tmpl_path)
                processed = renderer.process(data, ctx, self)
                return renderer.render(processed, ctx, self)

            # kind: name (named lookup)
            kind = data.pop("kind", None)
            if kind is None:
                # Infer from config defaults or built-in fallback
                if ctx.depth == 0:
                    kind = self.config_defaults.get("page", "page")
                else:
                    kind = self.config_defaults.get("section", "section")

            renderer = resolve_renderer(kind, jinja_env=self.jinja_env)
            processed = renderer.process(data, ctx, self)
            return renderer.render(processed, ctx, self)

        return str(data)

    # ------------------------------------------------------------------
    # Link processing
    # ------------------------------------------------------------------

    def _process_link(self, link: dict, ctx: NodeContext) -> dict:
        """Process a single link dict — resolve src, href, and content files."""
        link = copy.deepcopy(link)

        # src: path — content files can generate sub-pages via extensions.
        if "src" in link:
            src = link["src"]
            content_kind = self._content_renderer_key(src)
            if content_kind:
                link = self._process_content_link(link, ctx, kind=content_kind)
            elif src.endswith((".yml", ".yaml")):
                link = self._process_index_link(link, ctx)
            elif src.endswith(".pdf"):
                link = self._process_pdf_link(link, ctx)
            else:
                # Generic file — copy to output
                new_path = self.files.copy_file(src, src)
                if new_path:
                    link["href"] = new_path

        # href: url — external link, nothing to process
        if "href" not in link and "link" not in link:
            link.setdefault("href", "#")

        # Render description as markdown
        if "description" in link and isinstance(link["description"], str):
            link["description"] = build_markdown(
                raw=link["description"],
                builder=self,
                extensions=self.markdown_extensions,
            )

        # Process image
        if "image" in link:
            img = link["image"]
            img_src = img["src"] if isinstance(img, dict) else img
            new_path = self.files.copy_file(
                img_src,
                img_src,
                src_dir=ctx.assets_src_dir,
                target_dir=ctx.assets_target_dir or self.assets_dir,
            )
            if new_path:
                if isinstance(img, dict):
                    link["image"]["src"] = new_path
                else:
                    link["image"] = new_path

        return link

    def _content_renderer_key(self, src: str, preferred: str | None = None) -> str | None:
        """Resolve a content renderer key for a source file or explicit kind."""
        if preferred:
            candidates = [preferred, preferred if preferred.startswith(".") else f".{preferred}"]
        else:
            _, ext = os.path.splitext(src)
            candidates = [ext.lower()]
        for candidate in candidates:
            if candidate in self.content_renderers:
                return candidate
        return None

    def _process_content_link(self, link: dict, ctx: NodeContext, kind: str) -> dict:
        """Process a content link — render a sub-page."""
        src = link["src"]
        if src in self.processed_pages:
            # Already built — just return the URL
            slug = strip_suffixes(src, self._content_suffixes())
            link["href"] = prepend_baseurl(slug, baseurl=self.base_url)
            return link

        self.processed_pages.add(src)

        slug = strip_suffixes(src, self._content_suffixes())
        target_html = os.path.join(self.output_dir, f"{slug}.html")

        renderer_key = self._content_renderer_key(src, kind)
        if renderer_key is None:
            raise ValueError(f"No content renderer registered for '{src}' ({kind}).")
        content = self.content_renderers[renderer_key](self, src, ctx)

        if content:
            # Write the content page
            os.makedirs(os.path.dirname(target_html) or ".", exist_ok=True)
            with open(target_html, "w") as f:
                f.write(content)
            print(f"  Writing content page: {target_html}")

        link["href"] = prepend_baseurl(slug, baseurl=self.base_url)
        if "text" not in link:
            link["text"] = os.path.basename(slug).replace("-", " ").replace("_", " ").title()

        # Search indexing
        if ctx.search_links:
            self._add_search_item(
                slug=link["href"],
                url=link["href"],
                title=link.get("text", ""),
                description=link.get("description"),
            )

        return link

    def _content_suffixes(self) -> list[str]:
        suffixes = [key for key in self.content_renderers if key.startswith(".")]
        return sorted(suffixes, key=len, reverse=True)

    def _build_markdown_page(self, src: str, ctx: NodeContext, config_namespace: str = "markdown") -> str | None:
        """Build a content page from a markdown file."""
        if not os.path.isfile(src):
            print(f"  Warning: markdown file not found: {src}")
            return None

        with open(src) as fh:
            raw = fh.read()

        metadata_path = os.path.join(os.path.dirname(src), "page.yml")
        if not os.path.isfile(metadata_path):
            metadata_path = os.path.join(os.path.dirname(src), "metadata.yml")
        metadata = read_yaml(metadata_path) if os.path.isfile(metadata_path) else {}
        front_metadata, raw = split_yaml_front_matter(raw)
        metadata.update(front_metadata)
        if isinstance(metadata.get("config"), dict):
            self.extensions.configure_page_extensions(metadata["config"])

        body_html = build_markdown(
            raw=raw,
            builder=self,
            extensions=self.markdown_extensions,
            assets_src_dir=os.path.dirname(src),
            assets_target_dir=self.assets_dir,
        )

        # Render content page using content-page renderer
        renderer = resolve_renderer("content-page", jinja_env=self.jinja_env)
        page_data = {
            "content": body_html,
            "metadata": metadata,
            "title": metadata.get("title", os.path.basename(src)),
            "page_url": prepend_baseurl(strip_suffixes(src, self._content_suffixes()), self.base_url),
            "source_path": src,
            "_content_config_namespace": config_namespace,
        }
        # Inject global nav/footer from root
        if self.root_data:
            page_data["nav"] = self.root_data.get("nav")
            page_data["footer"] = self.root_data.get("footer")
            page_data["config"] = self.config
        return renderer.render(page_data, ctx, self)

    def _build_notebook_page(self, src: str, ctx: NodeContext) -> str | None:
        """Build a content page from a Jupyter notebook."""
        if not os.path.isfile(src):
            print(f"  Warning: notebook file not found: {src}")
            return None

        try:
            from webifier.renderers.notebook import convert_notebook

            body_html = convert_notebook(self, src, self.assets_dir)
        except Exception as exc:
            print(f"  Warning: notebook conversion failed for {src}: {exc}")
            return None

        renderer = resolve_renderer("content-page", jinja_env=self.jinja_env)
        page_data = {
            "content": body_html,
            "metadata": {},
            "title": os.path.basename(src),
        }
        if self.root_data:
            page_data["nav"] = self.root_data.get("nav")
            page_data["footer"] = self.root_data.get("footer")
            page_data["config"] = self.config
        # Colab link
        if self.repo_full_name:
            nb_dir = os.path.dirname(src)
            nb_name = strip_suffixes(os.path.basename(src), [".ipynb"])
            page_data["colab"] = (
                f"https://colab.research.google.com/github/"
                f"{self.repo_full_name}/blob/master/{nb_dir}/{nb_name}.ipynb"
            )
        return renderer.render(page_data, ctx, self)

    def _process_index_link(self, link: dict, ctx: NodeContext) -> dict:
        """Process a link to another index.yml — build the sub-page."""
        index_file = link["src"]
        index_data = self.build_page(index_file)

        if "text" not in link:
            link["text"] = (
                index_data.get("title")
                or index_data.get("header", {}).get("title")
                or os.path.basename(index_file)
            )
        if "description" not in link and "header" in index_data:
            desc = index_data["header"].get("description")
            if desc:
                link["description"] = desc

        slug = strip_suffixes(index_file, [".yml", ".yaml"])
        link["href"] = prepend_baseurl(slug, baseurl=self.base_url)
        return link

    def _process_pdf_link(self, link: dict, ctx: NodeContext) -> dict:
        """Process a PDF link — copy to output."""
        src = link["src"]
        new_path = self.files.copy_file(src, src)
        link["href"] = new_path if new_path else src
        link.setdefault("kind", "PDF")
        return link

    # ------------------------------------------------------------------
    # Markdown rendering
    # ------------------------------------------------------------------

    def render_markdown(self, raw: str, **kwargs) -> str:
        """Render markdown to HTML — convenience for templates."""
        return build_markdown(
            raw=raw,
            builder=self,
            extensions=self.markdown_extensions,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Background image processing
    # ------------------------------------------------------------------

    def resolve_background(self, data: dict, ctx: NodeContext) -> dict:
        """Resolve background image paths in a dict."""
        if "background" in data and isinstance(data["background"], str):
            bg = data["background"]
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", bg) or bg.startswith("//"):
                return data
            new_path = self.files.copy_file(
                bg,
                bg,
                src_dir=ctx.assets_src_dir,
                target_dir=ctx.assets_target_dir or self.assets_dir,
            )
            if new_path:
                data["background"] = new_path
        return data

    # ------------------------------------------------------------------
    # Search indexing
    # ------------------------------------------------------------------

    def _add_search_item(self, slug: str, url: str, title: str, description: str | None = None):
        """Add an item to the search index."""
        if slug in self.search_entries:
            return
        entry = {"title": title, "url": url}
        if description:
            entry["description"] = description
        self.search_entries[slug] = entry

    def _add_search_content(self, slug: str, content: str, title: str | None = None):
        """Add content to an existing search entry."""
        if slug not in self.search_entries:
            self.search_entries[slug] = {"title": title or slug, "url": slug}
        existing = self.search_entries[slug].get("content", "")
        cleaned = re.sub(r"<[^>]+>", "", str(content))
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            self.search_entries[slug]["content"] = f"{existing} {cleaned}" if existing else cleaned

    def save_search_json(self):
        """Write search.json to the output directory."""
        path = os.path.join(self.output_dir, "search.json")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        items = []
        for entry in self.search_entries.values():
            item = {"title": entry.get("title", ""), "url": entry.get("url", "")}
            if entry.get("content"):
                item["content"] = entry["content"]
            if entry.get("description"):
                item["description"] = re.sub(r"<[^>]+>", "", entry["description"])
            items.append(item)
        with open(path, "w") as f:
            json.dump(items, f, indent=2)
        print(f"  Writing search index: {path}")

    # ------------------------------------------------------------------
    # Top-level build
    # ------------------------------------------------------------------

    def build_page(self, index_file: str) -> dict:
        """Load and process an index file, writing the rendered HTML page."""
        if index_file in self.processed_pages:
            return read_yaml(index_file)

        # Ensure .yml extension
        if not index_file.endswith((".yml", ".yaml")):
            index_file = f"{index_file}.yml"

        if not os.path.isfile(index_file):
            raise FileNotFoundError(f"Index file not found: {index_file}")

        self._ensure_extensions_configured(index_file)

        print(f"Processing page: {index_file}")
        self.processed_pages.add(index_file)

        is_root = self.root_data is None
        data = load_and_resolve(index_file)
        assert isinstance(data, dict), f"Index file must be a YAML mapping, got {type(data)}"
        if not is_root and isinstance(data.get("config"), dict):
            self.extensions.configure_page_extensions(data["config"])

        # Process config on root page
        if is_root:
            self.config = self.extensions.apply_config(data.get("config", {}))
            self.config_defaults = self.config.get("defaults", {})
            search_cfg = self.config.get("search", False)
            if isinstance(search_cfg, bool):
                search_cfg = {"content": search_cfg, "links": search_cfg}
            self.config["search"] = search_cfg
            data["config"] = self.config

        # Build context
        slug = strip_suffixes(index_file, [".yml", ".yaml"])
        page_url = prepend_baseurl(slug, baseurl=self.base_url)
        ctx = NodeContext(
            key="root",
            depth=0,
            page_url=page_url,
            search_slug=page_url,
            search_content=self.config.get("search", {}).get("content", True),
            search_links=self.config.get("search", {}).get("links", True),
            assets_src_dir=os.path.dirname(index_file) or ".",
            assets_target_dir=self.assets_dir,
        )

        if is_root:
            self.root_data = data

        # Render the page. Set root_data first so sub-pages generated while
        # rendering the root can inherit global nav/footer/config.
        html = self.process_node(data, ctx)

        # Write HTML
        target_html = os.path.join(self.output_dir, f"{slug}.html")
        os.makedirs(os.path.dirname(target_html) or ".", exist_ok=True)
        with open(target_html, "w") as f:
            f.write(html)
        print(f"  Writing page: {target_html}")

        return data

    def build(self, index_file: str = "index.yml"):
        """Full site build — entry point.

        Builds the root page (which recursively builds sub-pages),
        copies assets, and writes the search index.
        """
        self._ensure_extensions_configured(index_file)

        # Copy user static files
        self.files.merge_dirs(".", self.output_dir, allow_list=["favicon.ico", "CNAME", "assets"])

        # Copy assets from enabled extensions.
        self._copy_extension_assets()

        self.extensions.run_hooks("before_build", index_file=index_file)

        # Build root page
        self.build_page(index_file)

        # Page-local extensions may register additional assets while pages render.
        self._copy_extension_assets()

        self.extensions.run_hooks("after_build", index_file=index_file)

        print(f"\nBuild complete! Output: {self.output_dir}/")


def _deep_merge(base: Any, override: Any) -> Any:
    """Recursively merge mappings, with override values winning."""
    if isinstance(base, dict) and isinstance(override, dict):
        result = copy.deepcopy(base)
        for key, value in override.items():
            result[key] = _deep_merge(result.get(key), value)
        return result
    if override is None:
        return copy.deepcopy(base)
    return copy.deepcopy(override)


def _normalize_page_nav_value(value: str, suffixes: list[str]) -> str:
    text = str(value).split("#", 1)[0].split("?", 1)[0].strip()
    if not text or "://" in text:
        return text
    text = text[1:] if text.startswith("/") else text
    if text.endswith("/"):
        return f"/{text}"
    text = strip_suffixes(text, suffixes)
    text = text if text.endswith(".html") else f"{text}.html"
    return f"/{strip_suffixes(text, 'index.html')}"
