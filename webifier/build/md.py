import markdown
import typing as th
import re
from .html import process_html as html_processor

URL_REGEX = re.compile('src=\"(?P<url>((http|ftp)s?:\/\/)?(-\.)?[\w\d\S]+)\"')


def build_markdown(
        raw: str,
        builder,
        assets_src_dir=None,
        assets_target_dir=None,
        extensions: th.Optional[th.Iterable[str]] = None,
        process_html=True,
        search_links=False,
):
    """Process raw markdown str and process its local assets if necessary
    """
    assets_target_dir = builder.assets_dir if assets_target_dir is None else assets_target_dir
    body = markdown.markdown(raw, extensions=extensions if extensions else builder.markdown_extensions)
    if process_html:
        return html_processor(builder, body, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
                              search_links=search_links)
    return body
