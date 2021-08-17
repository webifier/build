import markdown
from .io_utils import process_file
import typing as th
import re

URL_REGEX = re.compile('src=\"(?P<url>((http|ftp)s?:\/\/)?(-\.)?[\w\d\S]+)\"')


def build_markdown(
        builder,
        raw: str,
        extensions: th.Optional[th.Iterable[str]] = None
):
    """Process raw markdown str and process its local assets if necessary

    """
    body = markdown.markdown(raw, extensions=extensions)

    # move assets to `assets_dir`
    asset_remap = dict()
    for result in re.finditer(URL_REGEX, body):
        remap = process_file(result.group('url'), result.group('url'), target_dir=builder.assets_dir,
                             baseurl=builder.base_url)
        if remap:
            asset_remap[result.group('url')] = remap
    for src, remap in asset_remap.items():
        body = re.sub(f"src=\"{src}\"", f'src="{remap}"', body)
    return body
