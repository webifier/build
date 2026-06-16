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


def test_markdown_content_page_uses_sidecar_metadata_sections(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "page.md").write_text("# Body\n\nMarkdown content.", encoding="utf-8")
    (tmp_path / "notes" / "metadata.yml").write_text(
        """
title: Markdown With Authors
authors:
  kind: people
  content:
    - name: Ada Lovelace
      github: ada
      role: Author
comments:
  label: false
  kind: comments
""",
        encoding="utf-8",
    )
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
      people:
        uses: webifier.people
      comments:
        uses: webifier.comments
nav: false
docs:
  label: Docs
  content:
    - text: Page
      src: notes/page.md
""",
        encoding="utf-8",
    )

    Builder(base_url="", output_dir="out", templates_dir=".").build()

    html = (tmp_path / "out" / "notes" / "page.html").read_text(encoding="utf-8")
    assert "Markdown With Authors" in html
    assert "Ada Lovelace" in html
    assert "https://github.com/ada.png" in html
    assert ">GitHub<" in html


def test_content_pages_can_render_explicit_comments_sections(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "page.md").write_text("# Body\n\nMarkdown content.", encoding="utf-8")
    (tmp_path / "page.yml").write_text(
        """
comments:
  label: false
  kind: comments
""",
        encoding="utf-8",
    )
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
      comments:
        uses: webifier.comments
  comments:
    repo: owner/comments
    issue_term: pathname
nav: false
docs:
  label: Docs
  content:
    - text: Page
      src: page.md
""",
        encoding="utf-8",
    )

    Builder(base_url="", output_dir="out", templates_dir=".").build()

    html = (tmp_path / "out" / "page.html").read_text(encoding="utf-8")
    assert "utteranc.es/client.js" in html
    assert 'repo="owner/comments"' in html


def test_extension_can_consume_page_keys_before_section_rendering(tmp_path, monkeypatch):
    from webifier_extensions.registry import EXTENSIONS

    class WeatherExtension(Extension):
        id = "test.weather"

        def register(self, ctx):
            ctx.consume_page_key("weather", self.consume_weather)

        def consume_weather(self, builder, *, value, page, instance_name, **_kwargs):
            return {"forecast": value, "page_title": page.get("title"), "instance": instance_name}

    available = dict(EXTENSIONS)
    available["test.weather"] = WeatherExtension
    monkeypatch.setattr(ExtensionManager, "discover", lambda self: available)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "index.yml").write_text(
        """
title: Extension Test
config:
  webifier:
    extensions:
      site:
        uses: webifier.standard
      markdown:
        uses: webifier.markdown
      weather:
        uses: test.weather
nav: false
weather: cloudy
intro:
  label: Intro
  content: Visible content.
""",
        encoding="utf-8",
    )

    Builder(output_dir="out", templates_dir=".").build()

    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "Visible content." in html
    assert "cloudy" not in html
    assert "weather" not in html.lower()


def test_duplicate_page_key_consumers_require_override(monkeypatch):
    class OneExtension(Extension):
        id = "test.consume-one"
        page_keys = {"weather": lambda builder, **_kwargs: None}

    class TwoExtension(Extension):
        id = "test.consume-two"
        page_keys = {"weather": lambda builder, **_kwargs: None}

    monkeypatch.setattr(
        ExtensionManager,
        "discover",
        lambda self: {"test.consume-one": OneExtension, "test.consume-two": TwoExtension},
    )

    builder = Builder()
    with pytest.raises(ValueError, match="override: true"):
        builder.configure_extensions(
            {
                "webifier": {
                    "extensions": {
                        "one": {"uses": "test.consume-one"},
                        "two": {"uses": "test.consume-two"},
                    }
                }
            }
        )

    builder = Builder()
    builder.configure_extensions(
        {
            "webifier": {
                "extensions": {
                    "one": {"uses": "test.consume-one"},
                    "two": {"uses": "test.consume-two", "override": True},
                }
            }
        }
    )


def test_page_navigation_src_entries_resolve_to_generated_urls(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "one.md").write_text("# One", encoding="utf-8")
    (tmp_path / "two.md").write_text("# Two", encoding="utf-8")
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
  page_navigation:
    home:
      title: Home
      href: /
    items:
      - title: One
        src: one.md
      - title: Two
        src: two.md
nav: false
docs:
  label: Docs
  content:
    - text: One
      src: one.md
    - text: Two
      src: two.md
""",
        encoding="utf-8",
    )

    Builder(base_url="/site", output_dir="out", templates_dir=".").build()

    html = (tmp_path / "out" / "one.html").read_text(encoding="utf-8")
    assert 'href="/site/two.html"' in html


def test_page_navigation_can_be_overridden_per_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "one.md").write_text(
        """---
title: One
config:
  page_navigation:
    next:
      title: Custom Next
      href: /custom-next.html
---

# One
""",
        encoding="utf-8",
    )
    (tmp_path / "two.md").write_text(
        """---
title: Two
config:
  page_navigation:
    previous: false
---

# Two
""",
        encoding="utf-8",
    )
    (tmp_path / "hidden.md").write_text(
        """---
title: Hidden
config:
  page_navigation: false
---

# Hidden
""",
        encoding="utf-8",
    )
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
  page_navigation:
    home:
      title: Guide
      href: /
    items:
      - title: One
        src: one.md
      - title: Two
        src: two.md
      - title: Hidden
        src: hidden.md
nav: false
docs:
  label: Docs
  content:
    - text: One
      src: one.md
    - text: Two
      src: two.md
    - text: Hidden
      src: hidden.md
""",
        encoding="utf-8",
    )

    Builder(base_url="", output_dir="out", templates_dir=".").build()

    one_html = (tmp_path / "out" / "one.html").read_text(encoding="utf-8")
    two_html = (tmp_path / "out" / "two.html").read_text(encoding="utf-8")
    hidden_html = (tmp_path / "out" / "hidden.html").read_text(encoding="utf-8")
    assert "Custom Next" in one_html
    assert 'href="/custom-next.html"' in one_html
    assert "Back to One" not in two_html
    assert "Page navigation" not in hidden_html


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


def test_content_page_cleanup_normalizes_notebook_fragments():
    from webifier_extensions.standard.content_page import ContentPageRenderer

    html = """
<body class="jp-Notebook">
  <div align="center"><h1>AI - Test Page</h1><h2>Course header</h2></div>
  <hr>
  <h1>Test Page<a class="anchor-link" href="#test-page">¶</a></h1>
  <h2>Table of Contents</h2>
  <ul><li>Old contents</li></ul>
  <h2><font color="red">##</font></h2>
  <h2>Intro<a class="anchor-link" href="#intro">¶</a></h2>
  <p>First section.</p>
  <h2>Search</h2>
  <p>Second section.</p>
  <h2>Test Page</h2>
  <p>Duplicate title section text should remain.</p>
  <h3>Details</h3>
  <p>Third section.</p>
</body>
"""

    rendered = ContentPageRenderer().normalize_content(
        html,
        {"title": "Test Page", "metadata": {"header": {"title": "Test Page"}}},
        cleanup=True,
        toc=True,
    )

    assert "<body" not in rendered
    assert "AI - Test Page" not in rendered
    assert "Course header" not in rendered
    assert "Old contents" not in rendered
    assert "Table of Contents" in rendered
    assert "<h2>Test Page</h2>" not in rendered
    assert "Duplicate title section text should remain." in rendered
    assert "anchor-link" not in rendered
    assert "¶" not in rendered
    assert "<font" not in rendered
    assert "wf-content-toc" in rendered
    assert 'href="#intro"' in rendered


def test_content_page_cleanup_removes_old_course_cover_cells():
    from webifier_extensions.standard.content_page import ContentPageRenderer

    html = """
<body class="jp-Notebook">
<main>
  <div class="jp-Cell jp-MarkdownCell">
    <div><div align="center">
      Decision Tree
      Sharif University Of technology - Computer Engineering Depatment
      Artifical Intelligence - Dr. MH Rohban
      Spring 2021
    </div></div>
  </div>
  <div class="jp-Cell jp-MarkdownCell"><h2>Overview</h2><p>Real content.</p></div>
  <div class="jp-Cell jp-MarkdownCell"><h2>Operators</h2><p>More content.</p></div>
  <div class="jp-Cell jp-MarkdownCell"><h2>Entropy</h2><p>More content.</p></div>
</main>
</body>
"""

    rendered = ContentPageRenderer().normalize_content(
        html,
        {"title": "LN | Learning a Decision Tree", "metadata": {"header": {"title": "Learning a Decision Tree"}}},
        cleanup=True,
        toc=True,
    )

    assert "Sharif University" not in rendered
    assert "Artifical Intelligence" not in rendered
    assert "Spring 2021" not in rendered
    assert "Real content." in rendered
    assert "wf-content-toc" in rendered


def test_content_page_cleanup_demotes_slide_headings_and_excludes_math_headings():
    from webifier_extensions.standard.content_page import ContentPageRenderer

    html = """
<body>
  <main>
    <h1>Example</h1>
    <p>One.</p>
    <h1>Entities</h1>
    <p>Two.</p>
    <h1>$ V^*(s) = max_aQ^*(s,a) $</h1>
    <p>Math explanation.</p>
    <h1>$               =              $</h1>
    <h1>Preferences</h1>
    <p>Three.</p>
    <h1>Discounting</h1>
    <p>Four.</p>
    <h1>Optimal value functions</h1>
    <p>Five.</p>
    <h1>Comparing VI and PI</h1>
    <p>Six.</p>
  </main>
</body>
"""

    rendered = ContentPageRenderer().normalize_content(
        html,
        {"title": "Markov Decision Processes", "metadata": {"header": {"title": "Markov Decision Processes"}}},
        cleanup=True,
        toc=True,
    )

    assert "<h1" not in rendered
    assert "<h2" in rendered
    assert 'class="wf-math-display"' in rendered
    assert "max_aQ" in rendered
    assert "href=\"#$-" not in rendered
