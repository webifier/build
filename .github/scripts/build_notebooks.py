import os
from sys import argv
import glob

def build_notebook(file, targetdir):
    os.makedirs(targetdir, exist_ok=True)

    print(f'building {file} to {targetdir}')

    error = os.system(f"{jupyter_command} nbconvert --to html --output-dir='{targetdir}' {file}")
    if error:
        raise Exception(f"Error in building {file}")


def create_jekyll_text(notebook, title):
    return f'---\nlayout: notebook\ntitle: {title}\nnotebook: {notebook}\n---'


def create_jekyll_file(sourcedir, filename):
    text = create_jekyll_text(os.path.join(sourcedir, f'{filename}.html'), "Page Title")
    jekyll_path = os.path.join('./', *sourcedir.split('/')[1:], f'{filename}.html')   # ./a/b.html
    jekyll_dir, _ = os.path.split(jekyll_path)
    os.makedirs(jekyll_dir, exist_ok=True)
    with open(jekyll_path, 'w') as jekyll_file:
        jekyll_file.write(text)



jupyter_command = argv[1]

for file in glob.glob('notebooks/**/*.ipynb', recursive=True):
    sourcedir, filename = os.path.split(file)                   # notebooks/a, b.ipynb
    filename = filename.split('.')[0]                           # b

    targetdir = os.path.join('_includes', sourcedir)             # _include/notebooks/a
    build_notebook(file, targetdir)
    create_jekyll_file(sourcedir, filename)
    