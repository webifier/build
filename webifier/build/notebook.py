from bs4 import BeautifulSoup
import nbconvert
import nbformat
import os
import typing as th
from .html import process_html


def generate_notebook_html(builder, src: str, assets_dir: th.Optional[str] = None, search_links=False):
    """Generates notebook html body and move its assets to `assets_dir`

    Arguments:
        src {str} -- the path to the notebook file (with .ipynb)
        assets_dir {str} -- where to copy local assets (if None is provided no file will be copied)
        baseurl {str} -- base url to prepend to local links (dismissed if None is provided)
    Return:
        Generated body str
    """

    print(f'Building notebook {src} (assets:{assets_dir})!')
    assert os.path.isfile(src), f'Notebook {src} could not be found!'
    if assets_dir:
        os.makedirs(assets_dir, exist_ok=True)

    with open(src) as nb_file:
        nb_contents = nb_file.read()

    # convert using the ordinary exporter
    notebook = nbformat.reads(nb_contents, as_version=4)
    exporter = nbconvert.HTMLExporter()
    body, _ = exporter.from_notebook_node(notebook)

    soup = BeautifulSoup(body, 'html.parser')
    body = "".join(map(str, soup.select('#notebook-container')[0].contents))
    notebook_dir, _ = os.path.split(src)
    return process_html(builder, body, assets_target_dir=assets_dir, assets_src_dir=notebook_dir,
                        search_links=search_links)
