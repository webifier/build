from __future__ import annotations

from types import SimpleNamespace

from webifier.core.markdown import build_markdown


def test_markdown_preserves_math_delimiters_and_code():
    builder = SimpleNamespace(
        assets_dir="assets",
        markdown_extensions=("fenced_code", "codehilite"),
    )
    html = build_markdown(
        "Inline $h(n) \\leq c(n,a,n') + h(n')$.\n\n"
        "$\\begin{align}\na_b &= c+d\n\\end{align}$\n\n"
        "$$\n\\sum_i x_i\n$$\n\n"
        "`$not_math$`\n\n"
        "```python\nvalue = '$still_not_math$'\n```",
        builder,
        process_html=False,
    )

    assert "$h(n) \\leq c(n,a,n') + h(n')$" in html
    assert "\\begin{align}\na_b &= c+d\n\\end{align}" in html
    assert "$$\n\\sum_i x_i\n$$" in html
    assert "<code>$not_math$</code>" in html
    assert "$still_not_math$" in html
    assert "WEBIFIER_MATH" not in html


def test_old_github_math_images_become_mathjax_text():
    builder = SimpleNamespace(
        assets_dir="assets",
        markdown_extensions=("md_in_html",),
    )
    html = build_markdown(
        'For every <img src="https://render.githubusercontent.com/render/math?math=X_i%20%5Cleq%20Y_i%20+%20Z_i">.',
        builder,
    )

    assert 'render.githubusercontent.com/render/math' not in html
    assert "\\(X_i \\leq Y_i + Z_i\\)" in html
