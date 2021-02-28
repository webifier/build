import os
from sys import argv
import glob

target_root = argv[1]

for file in glob.glob('notebooks/**/*.ipynb', recursive=True):
    sourcedir, _ = os.path.split(file)
    targetdir = os.path.join(target_root, *sourcedir.split('/')[1:])
    os.makedirs(targetdir, exist_ok=True)
    print(f'building {file} to {targetdir}')
    error = os.system(f"$CONDA/bin/jupyter nbconvert --to html --output-dir='{targetdir}' {file}")
    if error:
        raise Exception(f"Error in building {file}")

