import os
from sys import argv
import glob

target_root = argv[1]

for file in glob.glob('notebooks/**/*.ipynb', recursive=True):
    sourcedir, _ = os.path.split(file)
    targetdir = os.path.join(target_root, *sourcedir.split('/')[1:])
    os.makedirs(targetdir, exist_ok=True)
    print(f'building {file} to {targetdir}')
    os.system(f"jupyter nbconvert --to html --output-dir='{targetdir}' {file}")

