import glob
from bs4 import BeautifulSoup
import nbconvert
import nbformat
import os
import re
import typing as th
from .io_utils import process_file, data_name
from .jekyll import create_jekyll_file, create_jekyll_content_header, get_colab_url


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


def process_notebook(builder, link):
    """Process notebook link object and generate the pointed notebook file

    Arguments:
        builder -- the calling builder object
        link {dict} -- pointing link object

    Return:
        Processed link object (now holding description and other information of the notebook and a static link)
    """
    notebook = link['notebook']  # path to notebook `{folder_name}`
    notebook_dir = notebook
    filename = os.path.join(notebook_dir, 'index.ipynb')

    # if metadata is not available don't copy it
    metadata_path = None
    if os.path.isfile(os.path.join(notebook_dir, 'metadata.yml')):
        metadata = builder.build_index(index_file=os.path.join(notebook_dir, 'metadata'), index_type='content')
        metadata_path = data_name(index_file=os.path.join(notebook_dir, 'metadata'), index_type='content')
    jekyll_targetdir = os.path.join(notebook, 'index.html')
    create_jekyll_file(
        target=jekyll_targetdir,
        header=create_jekyll_content_header(
            metadata_path=metadata_path,
            colab_url=get_colab_url(notebook, repo_full_name=builder.repo_full_name)
        ),
        body=generate_notebook_html(
            src=filename,
            assets_dir=builder.assets_dir,  # where to move notebook assets
            base_url=builder.base_url
        )
    )
    link['link'] = notebook if builder.base_url is None else (
        f'{builder.base_url}/{notebook}' if not builder.base_url.endswith('/') else f'{builder.base_url}{notebook}')
    return link
