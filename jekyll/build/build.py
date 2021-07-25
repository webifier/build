import os
import shutil
import re
import glob
from bs4 import BeautifulSoup
import nbconvert
import nbformat
from yaml_helper import read_yaml, save_yaml

# metadata file names will be like `{notebook_folder_name}`
BASE_INDEX_FILE = 'index.yml'
TARGET_INDEX_FILE = '_data/index.yml'
NOTEBOOKS_METADATA_DIR = '_data/notebooks'
NOTEBOOKS_DIR = 'notebooks'


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
    os.makedirs(f'{target_dir}{base_dir}', exist_ok=True)
    target = f'{target_dir}{target}'
    shutil.copy2(src, target)
    return target if baseurl is None else f'{baseurl}/{target}'


def build_notebook(src, build_dir, assets_dir):
    """Generates notebook html file and puts it into `build_dir` and move its assets to `assets_dir`"""

    print(f'Building notebook {src} to {build_dir} (assets:{assets_dir})!')
    assert os.path.isfile(src), f'Note'
    os.makedirs(build_dir, exist_ok=True)
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

        target_file = process_file(asset, asset, target_dir=assets_dir, baseurl=baseurl)  # todo: make right!
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

    build_dir = ('' if not build_dir else build_dir if build_dir.endswith('/') else f'{build_dir}/') + '/'.join(
        src.split('/')[:-1])
    os.makedirs(build_dir, exist_ok=True)
    with open(os.path.join(build_dir, 'index.html'), 'w') as output_file:
        output_file.write(body)


def create_jekyll_notebook_text(notebook, title, metadata_path=None, colab_url=None, chapter=None):
    metadata = f'metadata: {metadata_path}\n' if metadata_path is not None else ''
    colab = f'colab: {colab_url}\n' if colab_url is not None else ''
    chapter = f'chapter: {chapter}\n' if chapter else ''
    return f'---\nlayout: notebook\ntitle: {title}\nnotebook: {notebook}\n{metadata}{colab}{chapter}---'


def create_jekyll_home_text(index):
    return f'---\nlayout: home\nindex: {index}\n---'


def create_jekyll_file(target, text):
    basedir = '/'.join(target.split('/')[:-1])
    os.makedirs(basedir, exist_ok=True)
    with open(target, 'w') as jekyll_file:
        jekyll_file.write(text)


def process_person(person, image_src_dir=None, image_target_dir=None):
    assert isinstance(person, dict), \
        f'person objects, are expected to be dictionaries, {type(person)} provided instead!'
    image = person.get('image', None)
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
    return person


def process_metadata(notebook: str, metadata: dict):
    """
    Process notebook's metadata file and move it to `{NOTEBOOKS_METADATA_DIR}/{notebook | preprocessed}.yml`.
    This function is also responsible for loading up author image from their github profile if no image is provided.
    Author image files will also be moved to `assets/notebooks/{notebook | preprocessed}/files`.
    """
    data_name = notebook.replace('/', '_').replace(' ', '')
    for key, value in metadata.items():
        metadata[key] = build_object(value, image_key='background', image_src_dir=f'{NOTEBOOKS_DIR}/{notebook}',
                                     image_target_dir=f'assets/{NOTEBOOKS_DIR}/{notebook}')

    metadata = build_object(metadata, 'background')
    # moving metadata yaml to `_data`
    os.makedirs(NOTEBOOKS_METADATA_DIR, exist_ok=True)
    target_path = os.path.join(NOTEBOOKS_METADATA_DIR, data_name + '.yml')
    save_yaml(metadata, target_path)
    return data_name


def get_colab_url(notebook_dir, notebook_file_name='index'):
    base_url = 'https://colab.research.google.com/github/'
    return f'{base_url}{repo_full_name}/blob/master/notebooks/{notebook_dir}/{notebook_file_name}.ipynb'


def process_notebook(link):
    notebook = link['notebook']  # path to notebook `notebooks/{folder_name}`
    notebook_dir = os.path.join(NOTEBOOKS_DIR, notebook)
    filename = os.path.join(notebook_dir, 'index.ipynb')
    build_notebook(
        # todo: if no more than one notebook is found in the directory use that as index else raise exception
        src=filename,
        build_dir='_includes',  # where the notebook.html will reside
        assets_dir='assets',  # where to move notebook assets
    )

    # if metadata is not available don't copy it
    raw_metadata_path = os.path.join(notebook_dir, 'metadata.yml')
    metadata_path = None
    if os.path.isfile(raw_metadata_path):
        metadata = read_yaml(raw_metadata_path)
        metadata_path = process_metadata(notebook, metadata)

    jekyll_targetdir = os.path.join(NOTEBOOKS_DIR, notebook, 'index.html')
    create_jekyll_file(
        target=jekyll_targetdir,
        text=create_jekyll_notebook_text(
            notebook=jekyll_targetdir,
            title=f"{link.get('text', 'Notebook')}" if metadata_path is None else metadata.get(
                'title', link.get('text', 'Notebook')),
            chapter=None,  # todo: chapter=link, for adding extra functionality
            metadata_path=metadata_path,
            colab_url=get_colab_url(notebook)
        )
    )

    if remove_source:
        shutil.rmtree(notebook_dir)
    return link


def build_link(link, image_key=None, image_src_dir=None, image_target_dir='assets', sub_objects=None):
    if 'notebook' in link:
        link = process_notebook(link)  # in case some data was added to link descriptor later
    elif 'kind' in link and link['kind'] == 'person':
        link = process_person(link, image_src_dir=image_src_dir, image_target_dir=image_target_dir)
    if 'index' in link:
        index_file = read_yaml(f'{link["index"]}.yml')
        index_file = build_index(index_file)
        if 'title' in index_file:
            link['text'] = index_file['title']
        data_name = link["index"].replace('/', '_').replace(' ', '')
        save_yaml(index_file, f'_data/{data_name}.yml')
        link['link'] = f'{baseurl}/{link["index"]}.html'
        create_jekyll_file(f'{link["index"]}.html', create_jekyll_home_text(data_name))
    return link


def build_object(obj, image_key=None, image_src_dir=None, image_target_dir='assets', sub_objects=None):
    """
    Process the self replicating structure of objects in `index.yml`
    """
    # objects are either have descriptors or a list of link objects
    content = obj if 'content' not in obj else (
        obj.get('content', obj) if isinstance(obj, dict) else obj)

    # building object content
    if isinstance(content, list):
        # if object is a list of links
        for idx, item in enumerate(content):
            if 'kind' in obj and obj['kind'] == 'people':
                item['kind'] = 'person'
            content[idx] = build_link(item, image_src_dir=image_src_dir, image_target_dir=image_target_dir)
    if 'content' in obj:
        obj['content'] = content
    else:
        obj = content

    # processing sub objects of the same kind
    if sub_objects is not None:
        for sub in sub_objects if isinstance(sub_objects, list) else [sub_objects]:
            obj[sub] = build_object(obj, image_key, image_src_dir=image_src_dir, image_target_dir=image_target_dir,
                                    sub_objects=sub_objects)

    # building object (background) image
    if image_key is not None and image_key in obj:
        target_path = process_file(obj['background'], obj['background'], image_target_dir, baseurl)
        if target_path:
            obj[image_key] = target_path
    return obj


def build_index(index):
    """
    Process the self replicating structure of `index.yml` and look for notebook links and render them.
    """
    assert isinstance(index, dict), \
        f'index is supposed to be an object, got {type(index)}'
    index['title'] = index.get('title', 'Index')
    for key, value in index.items():
        if key in ['chapters', ]:
            continue
        index[key] = build_object(value, image_key='background')

    for idx, chapter in enumerate(index.get('chapters', [])):
        index['chapters'][idx] = build_index(chapter)

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

    print(f'baseurl: {baseurl}')
    print(f'remove_source: {remove_source}')
    print(f'repo_full_name: {repo_full_name}')

    save_yaml(build_index(read_yaml(args.index)), TARGET_INDEX_FILE)
