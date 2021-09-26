import os
import typing as th


def get_colab_url(notebook_dir, repo_full_name: str, notebook_file_name='index'):
    base_url = 'https://colab.research.google.com/github/'
    return f'{base_url}{repo_full_name}/blob/master/{notebook_dir}/{notebook_file_name}.ipynb'


def create_jekyll_content_header(metadata_path: th.Optional[str] = None, colab_url: th.Optional[str] = None):
    """Create header text of jekyll file

    Arguments:
        metadata_path {str} --the file name (w/o ".yml") of the metadata file
        colab_url {str} -- the colab url
        baseurl {str} -- base url to prepend to local links (dismissed if None is provided)
    Return:
        Generated body str
    """
    metadata = f'metadata: {metadata_path}\n' if metadata_path is not None else ''
    colab = f'colab: {colab_url}\n' if colab_url is not None else ''
    return f'---\nlayout: content\n{metadata}{colab}---\n'


def create_jekyll_home_header(index):
    return f'---\nlayout: home\nindex: {index}\n---'


def create_jekyll_file(target, header, body=None):
    # todo: rewrite with os.path
    basedir = '/'.join(target.split('/')[:-1])
    if basedir:
        os.makedirs(basedir, exist_ok=True)
    print('Writing jekyll file to', target)
    with open(target, 'w') as jekyll_file:
        jekyll_file.write(header)
        if body:
            jekyll_file.write(body)
