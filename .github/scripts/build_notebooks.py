import os
import shutil
import re
from sys import argv
import glob
import nbconvert
import nbformat


def build_notebook(source_file, targetdir):
    os.makedirs(targetdir, exist_ok=True)

    print(f'building {source_file} to {targetdir}')

    with open(source_file) as nb_file:
        nb_contents = nb_file.read()
    
    # Convert using the ordinary exporter
    notebook = nbformat.reads(nb_contents, as_version=4)
    exporter = nbconvert.HTMLExporter()
    body, _ = exporter.from_notebook_node(notebook)

    ### MOVE RESOURCE FILES

    sourcedir, _ = os.path.split(source_file)
    all_files = glob.glob(os.path.join(sourcedir, '*.*'), recursive=True)
    for asset in filter(lambda name: name != source_file, all_files):
        _, filename = os.path.split(asset)

        pattern = r'src=".*' + filename + r'"'
        if not re.search(pattern, body):
            continue

        target_file = os.path.join('assets', asset)
        target_dir, _ = os.path.split(target_file)
        os.makedirs(target_dir, exist_ok=True)
        
        print(f"copying {asset} to {target_file}")
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


def create_jekyll_text(notebook, title):
    return f'---\nlayout: notebook\ntitle: {title}\nnotebook: {notebook}\n---'


def create_jekyll_file(sourcedir, filename):
    text = create_jekyll_text(os.path.join(sourcedir, f'{filename}.html'), "Page Title")
    jekyll_path = os.path.join('./', *sourcedir.split('/')[1:], f'{filename}.html')   # ./a/b.html
    jekyll_dir, _ = os.path.split(jekyll_path)
    os.makedirs(jekyll_dir, exist_ok=True)
    with open(jekyll_path, 'w') as jekyll_file:
        jekyll_file.write(text)


baseurl = argv[1] if len(argv) > 1 else ""


for file in glob.glob('notebooks/**/*.ipynb', recursive=True):
    sourcedir, filename = os.path.split(file)                   # notebooks/a, b.ipynb
    filename = filename.split('.')[0]                           # b

    targetdir = os.path.join('_includes', sourcedir)             # _include/notebooks/a
    build_notebook(file, targetdir)
    create_jekyll_file(sourcedir, filename)
    