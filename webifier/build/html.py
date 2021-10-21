from bs4 import BeautifulSoup
import re
from .io_utils import process_file
import itertools

HREF_REGEX = re.compile('((?P<type>(index|pdf|md|notebook))=)?(?P<url>((http|ftp)s?:\/\/)?(-\.)?[\w\d\S]+)')


def find_all_tags(soup, tags: list, *args, **kwargs):
    return itertools.chain.from_iterable(soup.find_all(tag, *args, **kwargs) for tag in tags)


def process_html(builder, raw_html, assets_src_dir=None, assets_target_dir=None, search_links=False) -> str:
    assets_target_dir = assets_target_dir if assets_target_dir is not None else builder.assets_dir
    soup = BeautifulSoup(raw_html, features="html.parser")
    for anchor in soup.find_all('a'):
        anchor = process_html_anchor(
            builder, soup, anchor, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
            add_search_item=search_links)
    for src_tag in find_all_tags(soup, tags='img,audio,embed,iframe,script,source,track,video'.split(','), src=True):
        new_src = process_file(src_tag['src'], src_tag['src'], src_dir=assets_src_dir, target_dir=assets_target_dir,
                               baseurl=builder.base_url, base_output_dir=builder.output_dir)
        if new_src:
            src_tag['src'] = new_src
    return str(soup)


def process_html_anchor(builder, soup, anchor, assets_src_dir=None, assets_target_dir=None, add_search_item=False):
    link = {key: anchor[key] for key in anchor.attrs if key not in ['href', 'class']}
    if anchor.text:
        link['text'] = anchor.text
    if 'href' in anchor.attrs and anchor['href']:

        match_dict = re.match(HREF_REGEX, anchor['href']).groupdict()
        link[match_dict['type'] or 'link'] = match_dict['url']
        link = builder.build_link(link, assets_src_dir=assets_src_dir, add_search_item=add_search_item)
        anchor['href'] = link['link']
    if 'text' in link:
        anchor.string = link['text']
    if 'icon' in link:
        text = anchor.text
        anchor.clear()
        icon_tag = soup.new_tag('i')
        icon_tag['aria-hidden'] = "true"
        icon_tag['class'] = link['icon']
        anchor.append(icon_tag)
        anchor.append(f' {text}')
        del anchor['icon']
    if 'description' in link:
        anchor["data-bs-toggle"] = "tooltip"
        anchor["data-bs-html"] = "true"
        anchor["title"] = link['description']
    return anchor
