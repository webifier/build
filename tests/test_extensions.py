from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from webifier.core.base import RendererModule
from webifier.core.builder import Builder
from webifier.core.extensions import Extension, ExtensionManager

WORKSPACE = Path(__file__).resolve().parents[2]
EXTENSIONS_REPO = WORKSPACE / "extensions"
if str(EXTENSIONS_REPO) not in sys.path:
    sys.path.insert(0, str(EXTENSIONS_REPO))


def test_named_extensions_build_markdown_site(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "page.md").write_text("# Hello\n\nA markdown page.", encoding="utf-8")
    (tmp_path / "index.yml").write_text(
        """
title: Test Site
config:
  webifier:
    extensions:
      site:
        uses: webifier.standard
      markdown:
        uses: webifier.markdown
      search:
        uses: webifier.search
        content: true
        links: true
nav: false
docs:
  label: Docs
  content:
    - text: Page
      src: page.md
""",
        encoding="utf-8",
    )

    builder = Builder(output_dir="out", templates_dir=".")
    builder.build()

    assert (tmp_path / "out" / "index.html").is_file()
    assert (tmp_path / "out" / "page.html").is_file()
    search = json.loads((tmp_path / "out" / "search.json").read_text(encoding="utf-8"))
    assert any(item["title"] == "Page" for item in search)


def test_empty_baseurl_generates_rooted_nested_links(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "page.md").write_text(
        "[Child](md=nested/child.md)",
        encoding="utf-8",
    )
    (tmp_path / "nested" / "child.md").write_text("# Child", encoding="utf-8")
    (tmp_path / "index.yml").write_text(
        """
title: Test Site
config:
  webifier:
    extensions:
      site:
        uses: webifier.standard
      markdown:
        uses: webifier.markdown
nav: false
docs:
  label: Docs
  content:
    - text: Page
      src: nested/page.md
""",
        encoding="utf-8",
    )

    Builder(base_url="", output_dir="out", templates_dir=".").build()

    page_html = (tmp_path / "out" / "nested" / "page.html").read_text(encoding="utf-8")
    assert 'href="/nested/child.html"' in page_html


def test_extension_registration_requires_explicit_override(monkeypatch):
    class RendererA(RendererModule):
        def render(self, data, ctx, builder):
            return "a"

    class RendererB(RendererModule):
        def render(self, data, ctx, builder):
            return "b"

    class TestOneExtension(Extension):
        id = "test.one"
        renderers = {"test.override": RendererA}

    class TestTwoExtension(Extension):
        id = "test.two"
        renderers = {"test.override": RendererB}

    monkeypatch.setattr(
        ExtensionManager,
        "discover",
        lambda self: {"test.one": TestOneExtension, "test.two": TestTwoExtension},
    )

    builder = Builder()
    with pytest.raises(ValueError, match="override: true"):
        builder.configure_extensions(
            {
                "webifier": {
                    "extensions": {
                        "one": {"uses": "test.one"},
                        "two": {"uses": "test.two"},
                    }
                }
            }
        )

    builder = Builder()
    builder.configure_extensions(
        {
            "webifier": {
                "extensions": {
                    "one": {"uses": "test.one"},
                    "two": {"uses": "test.two", "override": True},
                }
            }
        }
    )


def test_extension_provider_must_be_object_or_class(monkeypatch):
    def old_factory():
        return None

    monkeypatch.setattr(
        ExtensionManager,
        "discover",
        lambda self: {"test.old-factory": old_factory},
    )

    builder = Builder()
    with pytest.raises(TypeError, match="Extension subclass or instance"):
        builder.configure_extensions(
            {
                "webifier": {
                    "extensions": {
                        "old": {"uses": "test.old-factory"},
                    }
                }
            }
        )


def test_head_hook_can_inject_from_page_content(tmp_path, monkeypatch):
    from webifier_extensions.registry import EXTENSIONS

    def render_head(
        builder,
        *,
        hook_context,
        page=None,
        ctx=None,
        instance_config=None,
        **_kwargs,
    ):
        assert hook_context.page is page
        assert hook_context.ctx is ctx
        assert hook_context.instance_name == "widget"
        wanted_section = instance_config["section"]
        section_keys = [section["key"] for section in page.get("_sections", [])]
        if wanted_section in section_keys:
            return '<script src="/assets/widget.js"></script>'
        return ""

    class WidgetExtension(Extension):
        id = "test.widget"
        hooks = {"head": [render_head]}

    available = dict(EXTENSIONS)
    available["test.widget"] = WidgetExtension
    monkeypatch.setattr(ExtensionManager, "discover", lambda self: available)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "index.yml").write_text(
        """
title: Hook Test
config:
  webifier:
    extensions:
      site:
        uses: webifier.standard
      markdown:
        uses: webifier.markdown
      widget:
        uses: test.widget
        section: target
nav: false
target:
  label: Target
  content: This page uses the widget.
""",
        encoding="utf-8",
    )

    Builder(output_dir="out", templates_dir=".").build()

    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert '<script src="/assets/widget.js"></script>' in html


def test_head_hook_can_inject_from_markdown_page_config(tmp_path, monkeypatch):
    from webifier_extensions.registry import EXTENSIONS

    def render_head(builder, *, config=None, **_kwargs):
        widget = (config or {}).get("widget", {})
        if widget.get("enabled"):
            return '<script src="/assets/page-widget.js"></script>'
        return ""

    class PageWidgetExtension(Extension):
        id = "test.page-widget"
        hooks = {"head": [render_head]}

    available = dict(EXTENSIONS)
    available["test.page-widget"] = PageWidgetExtension
    monkeypatch.setattr(ExtensionManager, "discover", lambda self: available)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "page.md").write_text(
        """---
title: Page Widget
config:
  widget:
    enabled: true
---

# Page
""",
        encoding="utf-8",
    )
    (tmp_path / "index.yml").write_text(
        """
title: Hook Test
config:
  webifier:
    extensions:
      site:
        uses: webifier.standard
      markdown:
        uses: webifier.markdown
      widget:
        uses: test.page-widget
nav: false
docs:
  label: Docs
  content:
    - text: Page
      src: page.md
""",
        encoding="utf-8",
    )

    Builder(output_dir="out", templates_dir=".").build()

    root_html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    page_html = (tmp_path / "out" / "page.html").read_text(encoding="utf-8")
    assert '<script src="/assets/page-widget.js"></script>' not in root_html
    assert '<script src="/assets/page-widget.js"></script>' in page_html


def test_notebook_page_uses_yaml_preface_metadata(tmp_path, monkeypatch):
    from webifier_extensions.notebook import extension as notebook_extension
    from webifier_extensions.registry import EXTENSIONS

    def render_head(builder, *, config=None, **_kwargs):
        widget = (config or {}).get("widget", {})
        if widget.get("enabled"):
            return '<script src="/assets/notebook-widget.js"></script>'
        return ""

    class NotebookWidgetExtension(Extension):
        id = "test.notebook-widget"
        hooks = {"head": [render_head]}

    available = dict(EXTENSIONS)
    available["test.notebook-widget"] = NotebookWidgetExtension
    monkeypatch.setattr(ExtensionManager, "discover", lambda self: available)
    monkeypatch.setattr(
        notebook_extension,
        "convert_notebook",
        lambda builder, src, assets_dir: (
            "<p>Notebook body</p>",
            {
                "title": "Notebook Page",
                "header": {"title": "Notebook Header"},
                "nav": False,
                "config": {"widget": {"enabled": True}},
            },
        ),
    )
    monkeypatch.chdir(tmp_path)

    (tmp_path / "analysis.ipynb").write_text("{}", encoding="utf-8")
    (tmp_path / "index.yml").write_text(
        """
title: Hook Test
config:
  webifier:
    extensions:
      site:
        uses: webifier.standard
      markdown:
        uses: webifier.markdown
      notebook:
        uses: webifier.notebook
      widget:
        uses: test.notebook-widget
nav:
  content:
    - text: Root
      link: /
docs:
  label: Docs
  content:
    - text: Analysis
      src: analysis.ipynb
""",
        encoding="utf-8",
    )

    Builder(output_dir="out", templates_dir=".").build()

    page_html = (tmp_path / "out" / "analysis.html").read_text(encoding="utf-8")
    assert "<title>Notebook Page</title>" in page_html
    assert "Notebook Header" in page_html
    assert '<script src="/assets/notebook-widget.js"></script>' in page_html
    assert '<nav class="px-2 navbar' not in page_html


def test_notebook_first_markdown_cell_yaml_preface_is_removed(tmp_path):
    import nbformat
    from webifier_extensions.notebook.converter import read_notebook_with_metadata

    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                """---
title: Notebook Title
header:
  title: Notebook Header
---

# Visible Notebook Heading
"""
            ),
            nbformat.v4.new_code_cell("1 + 1"),
        ]
    )
    path = tmp_path / "analysis.ipynb"
    nbformat.write(notebook, path)

    parsed, metadata = read_notebook_with_metadata(str(path))

    assert metadata["title"] == "Notebook Title"
    assert metadata["header"]["title"] == "Notebook Header"
    assert parsed["cells"][0]["source"].startswith("# Visible Notebook Heading")
    assert "title: Notebook Title" not in parsed["cells"][0]["source"]
