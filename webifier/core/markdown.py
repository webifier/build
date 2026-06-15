from __future__ import annotations

import re
import typing as th
from urllib.parse import unquote

import markdown

from .html import process_html as html_processor

MATH_PATTERNS = (
    re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.DOTALL),
    re.compile(r"\\\[(.+?)\\\]", re.DOTALL),
    re.compile(r"\\\((.+?)\\\)", re.DOTALL),
    re.compile(r"(?<!\\)\$\s*\\begin\{([a-zA-Z*]+)\}.*?\\end\{\1\}\s*(?<!\\)\$", re.DOTALL),
    re.compile(r"\\begin\{([a-zA-Z*]+)\}.*?\\end\{\1\}", re.DOTALL),
    re.compile(r"(?<!\\)(?<!\$)\$(?![\s$]|@@WEBIFIER_MATH_)(?:\\.|[^\n\\$])+?(?<![\s\\])\$(?!\$)"),
)
FENCED_CODE_PATTERN = re.compile(r"(^|\n)(`{3,}|~{3,})[^\n]*\n.*?\n\2[ \t]*(?=\n|$)", re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"(`+)(.+?)(?<!`)\1", re.DOTALL)
GITHUB_MATH_IMAGE_PATTERN = re.compile(
    r"<img\s+[^>]*src=(['\"])https://render\.githubusercontent\.com/render/math\?math=(.*?)\1[^>]*>",
    re.IGNORECASE | re.DOTALL,
)


def build_markdown(
    raw: str,
    builder,
    assets_src_dir=None,
    assets_target_dir=None,
    extensions: th.Iterable[str] | None = None,
    process_html: bool = True,
    search_links: bool = False,
) -> str:
    assets_target_dir = builder.assets_dir if assets_target_dir is None else assets_target_dir
    code_spans: list[str] = []
    math_spans: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_spans.append(match.group(0))
        return f"@@WEBIFIER_CODE_{len(code_spans) - 1}@@"

    def stash_math(match: re.Match[str]) -> str:
        math_text = match.group(0)
        if (
            math_text.startswith("$")
            and math_text[1:].lstrip().startswith("\\begin")
            and math_text.rstrip().endswith("$")
        ):
            math_text = math_text[1 : len(math_text.rstrip()) - 1].strip()
        math_spans.append(math_text)
        return f"@@WEBIFIER_MATH_{len(math_spans) - 1}@@"

    raw = GITHUB_MATH_IMAGE_PATTERN.sub(lambda match: f"\\({unquote(match.group(2))}\\)", raw)
    protected = FENCED_CODE_PATTERN.sub(stash_code, raw)
    protected = INLINE_CODE_PATTERN.sub(stash_code, protected)
    for pattern in MATH_PATTERNS:
        protected = pattern.sub(stash_math, protected)
    for index, code in enumerate(code_spans):
        protected = protected.replace(f"@@WEBIFIER_CODE_{index}@@", code)

    body = markdown.markdown(protected, extensions=extensions if extensions else builder.markdown_extensions)
    for index, math_text in enumerate(math_spans):
        placeholder = f"@@WEBIFIER_MATH_{index}@@"
        body = body.replace(f"<p>{placeholder}</p>", math_text)
        body = body.replace(placeholder, math_text)
    if process_html:
        return html_processor(
            builder,
            body,
            assets_src_dir=assets_src_dir,
            assets_target_dir=assets_target_dir,
            search_links=search_links,
        )
    return body
