import os
from sys import argv
import glob

def create_jekyll(notebook):
    return f'''---
layout: notebook
notebook: {notebook}
---
'''

jupyter_command = argv[1]
target_root = argv[2]

for file in glob.glob('notebooks/**/*.ipynb', recursive=True):
    sourcedir, filename = os.path.split(file)
    filename = filename.split('.')[0]

    splitted = sourcedir.split('/')[1:]
    path = os.path.join(*splitted) if len(splitted) else '.'

    targetdir = os.path.join(target_root, path)

    os.makedirs(targetdir, exist_ok=True)
    print(f'building {file} to {targetdir}')
    error = os.system(f"{jupyter_command} nbconvert --to html --output-dir='{targetdir}' {file}")
    if error:
        raise Exception(f"Error in building {file}")

    os.makedirs(path, exist_ok=True)
    jekyll_path = os.path.join(path, f'{filename}.html')
    jekyll_file_text = create_jekyll(jekyll_path)
    with open(jekyll_path, 'w') as jekyll_file:
        jekyll_file.write(jekyll_file_text)
