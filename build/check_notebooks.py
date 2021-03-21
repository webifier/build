import os
from imageio import imread
from yaml_helper import read_yaml

IMAGE_MAX_SIZE = float(os.environ.get('IMAGE_MAX_SIZE', float('inf')))

contents = read_yaml('_data/content.yml')

for chapter in contents:
    for note in chapter['notes']:
        if 'notebook' not in note:
            continue
        
        print(f"Checking {chapter['title']} -> {note['title']}")

        assert isinstance(note['notebook'], str),\
            f"Expected notebook name to be string, got {type(note['notebook'])}"

        assert ' ' not in note['notebook'],\
            f"Expected notebook name to contain no whitespaces."

        notebook_dir = os.path.join('notebooks', note['notebook'])
        notebook_file = os.path.join(notebook_dir, 'index.ipynb')

        assert os.path.exists(notebook_file),\
            f"Notebook file {notebook_file} not found!"

        notebook_authors_file = os.path.join(notebook_dir, 'authors/metadata.yml')

        assert os.path.exists(notebook_authors_file),\
            f"Authors metadata file {notebook_authors_file} not found!"

        authors = read_yaml(notebook_authors_file)

        assert isinstance(authors, list),\
            f"Expected authors metadata file to be a list of authors"

        for author in authors:
            assert isinstance(author, dict),\
                f"Expected author to be an object, Got {type(author)}"

            assert 'name' in author,\
                f"Author object must contain name field"

            assert 'image' in author,\
                f"Author object must contain image field"

            author_image_file = os.path.join(notebook_dir, 'authors', author['image'])

            assert os.path.exists(author_image_file)

            assert os.path.getsize(author_image_file) <= IMAGE_MAX_SIZE,\
                f"Size of images must be less than {IMAGE_MAX_SIZE} bytes. Image: {author_image_file}"

            image = imread(author_image_file)

            assert image.shape[0] == image.shape[1],\
                f'Expected image shape to be square, got shape {image.shape}'

            assert 'role' in author,\
                f"Author object must contain role field"
