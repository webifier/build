import glob
from bs4 import BeautifulSoup
import nbconvert
import nbformat
import os
import re
import typing as th
from .io_utils import process_file


def generate_notebook_html(src: str, assets_dir: th.Optional[str] = None, base_url: th.Optional[str] = None):
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

    # find & move resource files
    notebook_dir, _ = os.path.split(src)
    all_files = glob.glob(os.path.join(
        notebook_dir, '**', '*.*'), recursive=True)
    for asset in filter(lambda name: name != src, all_files):
        _, filename = os.path.split(asset)

        pattern = r'src=".*' + filename + r'"'
        if not re.search(pattern, body):
            continue

        target_file = process_file(asset, asset, target_dir=assets_dir, baseurl=base_url)
        if target_file:
            body = re.sub(pattern, f'src="{target_file}"', body)
    # replace attachment sources
    images = {}
    for cell in notebook['cells']:
        if 'attachments' in cell:
            attachments = cell['attachments']
            for filename, attachment in attachments.items():
                for mime, base64 in attachment.items():
                    images[f'attachment:{filename}'] = f'data:{mime};base64,{base64}'
    for src, base64 in images.items():
        body = body.replace(f'src="{src}"', f'src="{base64}"')

    return body

