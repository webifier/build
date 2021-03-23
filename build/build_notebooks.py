import os
import shutil
import re
from sys import argv
import glob
from bs4 import BeautifulSoup
import nbconvert
import nbformat
from yaml_helper import read_yaml


def build_notebook(source_file, targetdir):
    os.makedirs(targetdir, exist_ok=True)

    print(f'building {source_file} to {targetdir}')

    with open(source_file) as nb_file:
        nb_contents = nb_file.read()
    
    # Convert using the ordinary exporter
    notebook = nbformat.reads(nb_contents, as_version=4)
    exporter = nbconvert.HTMLExporter()
    body, _ = exporter.from_notebook_node(notebook)

    soup = BeautifulSoup(body, 'html.parser')
    body = "".join(map(str, soup.select('#notebook-container')[0].contents))

    ### MOVE RESOURCE FILES

    sourcedir, _ = os.path.split(source_file)
    all_files = glob.glob(os.path.join(sourcedir, '**', '*.*'), recursive=True)
    for asset in filter(lambda name: name != source_file, all_files):
        _, filename = os.path.split(asset)

        pattern = r'src=".*' + filename + r'"'
        if not re.search(pattern, body):
            continue

        target_file = os.path.join('assets', asset)
        target_dir, _ = os.path.split(target_file)
        os.makedirs(target_dir, exist_ok=True)
        
        print(f"copying {asset} to {target_file} with baseurl={baseurl}/")
        shutil.copy2(asset, target_file)
        body = re.sub(pattern, f'src="{baseurl}/{target_file}"', body)


    ### REPLACE ATTACHMENTS
    images = {}
    for cell in notebook['cells']:
        if 'attachments' in cell:
            attachments = cell['attachments']
            for filename, attachment in attachments.items():
                for mime, base64 in attachment.items():
                    images[f'attachment:{filename}'] = f'data:{mime};base64,{base64}'
    for src, base64 in images.items():
        body = body.replace(f'src="{src}"', f'src="{base64}"')
    
    with open(os.path.join(targetdir, 'index.html'), 'w') as output_file:
        output_file.write(body)


def create_jekyll_text(notebook, title, author_path, colab_url):
    return f'---\nlayout: notebook\ntitle: {title}\nnotebook: {notebook}\nauthors: {author_path}\ncolab: {colab_url}\n---'


def create_jekyll_file(sourcedir, targetdir, title, filename, author_path, colab_url):
    text = create_jekyll_text(os.path.join(sourcedir, f'{filename}.html'), title, author_path, colab_url)
    jekyll_path = os.path.join(targetdir, f'{filename}.html')   # notebooks/a/b.html
    with open(jekyll_path, 'w') as jekyll_file:
        jekyll_file.write(text)


def move_author_data(sourcedir, authors):
    data_name = sourcedir.split('/')[-1]
    datadir = '_data/authors'
    os.makedirs(datadir, exist_ok=True)
    shutil.copy2(
        os.path.join(sourcedir, 'authors/metadata.yml'),
        os.path.join(datadir, data_name + '.yml'))

    imagesdir = 'assets/images/people'

    os.makedirs(imagesdir, exist_ok=True)
    for author in authors:
        shutil.copy2(
            os.path.join(sourcedir, 'authors', author['image']),
            os.path.join(imagesdir, author['image']))
    
    return data_name


def get_colab_url(notebook):
    return f'https://colab.research.google.com/github/SUT-AI/LectureNotes/blob/master/notebooks/{notebook}/index.ipynb'


def build_note(chapter, note):
    notebook = note['notebook']
    sourcedir = os.path.join('notebooks', notebook)
    filename = 'index'
    notebook_path = os.path.join(sourcedir, filename + '.ipynb')
    assert os.path.exists(notebook_path), f"{notebook_path} not found!"

    targetdir = os.path.join('_includes', sourcedir)             # _include/notebooks/a
    build_notebook(notebook_path, targetdir)
    authors = read_yaml(os.path.join(sourcedir, 'authors/metadata.yml'))
    author_path = move_author_data(sourcedir, authors)
    jekyll_targetdir = os.path.join('notebooks', chapter['id'], notebook)
    os.makedirs(jekyll_targetdir, exist_ok=True)
    colab_url = get_colab_url(notebook)
    create_jekyll_file(sourcedir, jekyll_targetdir, f"{chapter['title']} - {note['title']}", filename, author_path, colab_url)

baseurl = argv[1] if len(argv) > 1 else ""

contents = read_yaml('_data/content.yml')

for chapter in contents:
    for note in chapter['notes']:
        if 'notebook' not in note:
            continue
        
        print(f"Building {chapter['title']} -> {note['title']}")
        build_note(chapter, note)
