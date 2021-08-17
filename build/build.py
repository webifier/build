import os
import shutil
import re
import glob
from bs4 import BeautifulSoup
import markdown
import nbconvert
import nbformat
from yaml_helper import read_yaml, save_yaml

# metadata file names will be like `{notebook_folder_name}`
BASE_INDEX_FILE = 'index'
TARGET_INDEX_FILE = '_data/index.yml'


# NOTEBOOKS_METADATA_DIR = '_data/notebooks'
def data_name(index_file, index_type):
    return index_file.replace('/', '_').replace(' ', '')


def process_file(src, target, src_dir=None, target_dir=None, baseurl=None):
    """
    Process file and move it to target dir only if it is located locally (return True upon move).
    """
    if '://' in src:
        return False
    base_dir = '/'.join(target.split('/')[:-1])
    target_dir = '' if not target_dir else (target_dir if target_dir.endswith('/') else f'{target_dir}/')
    src = src if not src_dir else (f'{src_dir}{src}' if src_dir.endswith('/') else f'{src_dir}/{src}')
    assert os.path.isfile(src), f'{src} file does not exist!'
    if f'{target_dir}{base_dir}':
        os.makedirs(f'{target_dir}{base_dir}', exist_ok=True)
    target = f'{target_dir}{target}'
    shutil.copy2(src, target)
    return target if baseurl is None else (f'{baseurl}/{target}' if not baseurl.endswith(
        '/') else f'{baseurl}{target}')


def build_notebook(src, assets_dir):
    """Generates notebook html body and move its assets to `assets_dir`"""

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

        target_file = process_file(asset, asset, target_dir=assets_dir, baseurl=baseurl)
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


def build_markdown(raw: str, assets_dir):
    body = markdown.markdown(raw, extensions=['md_in_html', 'codehilite', 'fenced_code', 'tables', 'attr_list'])
    return body


def create_jekyll_content_header(metadata_path=None, colab_url=None):
    metadata = f'metadata: {metadata_path}\n' if metadata_path is not None else ''
    colab = f'colab: {colab_url}\n' if colab_url is not None else ''
    return f'---\nlayout: content\n{metadata}{colab}---'


def create_jekyll_home_header(index):
    return f'---\nlayout: home\nindex: {index}\n---'


def create_jekyll_file(target, header, body=None):
    basedir = '/'.join(target.split('/')[:-1])
    if basedir:
        os.makedirs(basedir, exist_ok=True)
    print('Writing jekyll file to', target)
    with open(target, 'w') as jekyll_file:
        jekyll_file.write(header)
        if body:
            jekyll_file.write(body)


def process_person(person, image_src_dir=None, image_target_dir=None):
    assert isinstance(person, dict), \
        f'person objects, are expected to be dictionaries, {type(person)} provided instead!'
    image = person.get('image', None)
    # build contact links
    for idx, contact_info in enumerate(person.get('contact', [])):
        person['contact'][idx] = build_link(contact_info, None)
        if 'github.com' in contact_info['link']:
            # if no image was provided use person github profile picture instead
            image = f"{contact_info['link']}.png"
    if 'image' in person:
        # copy person's static profile image into assets
        src = person['image'] if image_src_dir is None else f'{image_src_dir}/{person["image"]}'
        target = person['image'] if image_target_dir is None else f'{image_target_dir}/{person["image"]}'
        image = process_file(src, target, baseurl=baseurl)
    else:
        for contact_info in person.get('contact', []):
            if 'github.com' in contact_info['link']:
                # if no image was provided use person github profile picture instead
                image = f"{contact_info['link']}.png"
                break
    if image:
        person['image'] = image

    # process bio markdown
    if 'bio' in person:
        person['bio'] = build_markdown(person['bio'], image_target_dir)
    return person


def get_colab_url(notebook_dir, notebook_file_name='index'):
    base_url = 'https://colab.research.google.com/github/'
    return f'{base_url}{repo_full_name}/blob/master/{notebook_dir}/{notebook_file_name}.ipynb'


def process_notebook(link):
    notebook = link['notebook']  # path to notebook `{folder_name}`
    notebook_dir = notebook
    filename = os.path.join(notebook_dir, 'index.ipynb')

    # if metadata is not available don't copy it
    metadata_path = None
    if os.path.isfile(os.path.join(notebook_dir, 'metadata.yml')):
        metadata = build_index(index_file=os.path.join(notebook_dir, 'metadata'), index_type='content')
        metadata_path = data_name(index_file=os.path.join(notebook_dir, 'metadata'), index_type='content')
    jekyll_targetdir = os.path.join(notebook, 'index.html')
    create_jekyll_file(
        target=jekyll_targetdir,
        header=create_jekyll_content_header(
            metadata_path=metadata_path,
            colab_url=get_colab_url(notebook)
        ),
        body=build_notebook(
            # todo: if no more than one notebook is found in the directory use that as index else raise exception
            src=filename,
            assets_dir='assets',  # where to move notebook assets
        )
    )
    link['link'] = notebook if baseurl is None else (f'{baseurl}/{notebook}' if not baseurl.endswith(
        '/') else f'{baseurl}{notebook}')
    if remove_source:
        shutil.rmtree(notebook_dir)
    return link


def build_link(link, image_key=None, assets_src_dir=None, assets_target_dir='assets'):
    if 'notebook' in link:
        link = process_notebook(link)  # in case some data was added to link descriptor later
    elif 'kind' in link and link['kind'] == 'person':
        link = process_person(link, image_src_dir=assets_src_dir, image_target_dir=assets_target_dir)
    elif 'index' in link:
        index = build_index(index_file=link['index'])
        if 'text' not in link:
            if 'title' in index:
                link['text'] = index['title']
            elif 'header' in index and 'title' in index['header']:
                link['text'] = index['header']['title']
        if 'description' not in link and 'header' in index and 'description' in index['header']:
            link['description'] = index['header']['description']
        link['link'] = f'{baseurl}/{link["index"]}.html' if not link["index"].endswith('index') else \
            f'{baseurl}/{"/".join(link["index"].split("/")[:-1])}'
    elif 'pdf' in link:
        file_path = process_file(link['pdf'], link['pdf'], target_dir='assets', baseurl=baseurl)
        if file_path:
            link['pdf'] = file_path
    else:
        # processing markdown syntax
        if 'description' in link:
            link['description'] = build_markdown(link['description'], assets_target_dir)
    return link


def build_object(obj, image_key=None, assets_src_dir=None, assets_target_dir='assets'):
    """
    Process the self replicating structure of objects in `index.yml`
    """
    # objects are either have descriptors or a list of link objects
    content = obj if isinstance(obj, dict) and 'content' not in obj else (
        obj.get('content', obj) if isinstance(obj, dict) else obj)

    # building object content
    if isinstance(content, list):
        # if object is a list of other objects
        for idx, item in enumerate(content):
            if 'kind' in obj and obj['kind'] == 'people':
                item['kind'] = 'person'
            if 'kind' in obj and obj['kind'] == 'chapters':
                content[idx] = build_index(item)
            else:
                content[idx] = build_link(item, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir)
    elif isinstance(obj, dict) and 'content' in obj:
        for key, value in obj.items():
            if key in ['label']:
                continue
            if key == 'content':
                content = build_object(
                    obj['content'], image_key, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir)
                continue
            obj[key] = build_object(
                value, image_key, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir)
    elif isinstance(obj, str):
        return build_markdown(obj, assets_target_dir)
    else:
        return obj
    # processing markdown
    if 'content' in obj:
        obj['content'] = content
    else:
        obj = content

    # building object (background) image
    if image_key is not None and image_key in obj:
        target_path = process_file(obj[image_key], obj[image_key], src_dir=assets_src_dir, target_dir=assets_target_dir,
                                   baseurl=baseurl)
        if target_path:
            obj[image_key] = target_path
    return obj


def build_index(index: dict = None, index_file: str = None, target_data_file: str = None, index_type='index'):
    """
    Process the self replicating structure of `index.yml` and look for notebook links and render them.
    """
    assert index_file is not None or index is not None, f'Either index or index_file should be specified!'
    if index is None:
        assert os.path.isfile(f'{index_file}.yml'), \
            f"{index_type.capitalize()} file {f'{index_file}.yml'} could not be found!"
        index = read_yaml(f'{index_file}.yml')
        if index_file in checked_indices:
            return index
        print(f'Processing {index_type}', index_file)
        checked_indices.add(index_file)

    assert isinstance(index, dict), \
        f'index is supposed to be an object, got {type(index)}'
    if 'title' not in index and 'header' in index and 'title' in index['header']:
        index['title'] = index['header']['title']
    index['title'] = index.get('title', index_type.capitalize())
    for key, value in index.items():
        if key in ['title']:
            continue
        index[key] = build_object(value, image_key='background')

    if index_file is not None:
        # save data file
        save_yaml(index,
                  f'_data/{data_name(index_file, index_type)}.yml' if target_data_file is None else target_data_file)
        # create and save html file
        if index_type == 'index':
            create_jekyll_file(f'{index_file}.html', create_jekyll_home_header(data_name(index_file, index_type)))

    return index


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Build index.')
    parser.add_argument('--remove-source', dest='remove_source',
                        action='store_true', default=False, help='Remove source notebook files')
    parser.add_argument('--baseurl', dest='baseurl', default="",
                        help='Baseurl of deploying site')
    parser.add_argument('--repo_full_name',
                        dest='repo_full_name', help='user/repo_name')
    parser.add_argument('--index',
                        dest='index', help='index.yml file path', default=BASE_INDEX_FILE)
    args = parser.parse_args()
    baseurl = args.baseurl
    remove_source = args.remove_source
    repo_full_name = args.repo_full_name

    checked_indices = set()
    print(f'baseurl: {baseurl}')
    print(f'remove_source: {remove_source}')
    print(f'repo_full_name: {repo_full_name}')

    build_index(index_file=args.index, target_data_file=TARGET_INDEX_FILE)
