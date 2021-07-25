import os
import warnings
from yaml_helper import read_yaml

IMAGE_MAX_SIZE = float(os.environ.get('IMAGE_MAX_SIZE', float('inf')))
DEFAULT_INDEX_DATA_PATH = 'index.yml'


def validate_link(link, object_name='Link'):
    assert isinstance(link, dict), \
        f"{object_name} object,\n{link}\n is supposed to be object, got {type(link)}"

    media_count = ('link' in link) + ('notebook' in link) + ('pdf' in link) + ('md' in link)
    assert media_count <= 1, \
        f'{object_name} object,\n{link}\n is supposed to have only a single media source, ' \
        f'{media_count} provided instead!'

    # check local links
    if 'notebook' in link and '://' not in link['notebook']:
        notebook_dir = link["notebook"]
        notebook_file = os.path.join(notebook_dir, 'index.ipynb')

        assert os.path.exists(notebook_file), \
            f"Notebook file {notebook_file}, specified in {object_name} object,\n{link}\n could not be found!"

        notebook_metadata_file = os.path.join(notebook_dir, 'metadata.yml')

        if not os.path.exists(notebook_metadata_file):
            assert 'text' in link or 'icon' in link, \
                f'No text or icon is provided for notebook {link["notebook"]} in {object_name} object,\n{link}\n ' \
                f'with no metadata!'
            warnings.warn(
                f'Notebook metadata file {notebook_metadata_file} specified for {link["notebook"]},'
                f" in {object_name} object,\n{link}\n could not be found!", UserWarning)
        else:
            metadata = read_yaml(notebook_metadata_file)
            assert isinstance(metadata, dict), \
                f"Expected metadata file for {link['notebook']}, to be an object containing " \
                f"[author(s), name, (description), ...]"
            authors_list = metadata.get('authors', [])
            authors_list = authors_list if 'content' not in authors_list else authors_list.get('content', [])
            validate_image(metadata.get('authors', dict()), 'background')
            if not authors_list:
                warnings.warn(f"No author was specified for notebook {link['notebook']}", UserWarning)
            for author in authors_list:
                validate_author_data(author)

    if 'index' in link:
        assert os.path.isfile(f"{link['index']}.yml"), f'Index file {link["index"]} could not be found!'
        validate_index(read_yaml(f"{link['index']}.yml"))

    if 'pdf' in link:
        assert os.path.isfile(link['pdf']), f'PDF file {link["pdf"]} could not be found!'


def validate_image(obj, obj_name='Object', key='image', force_present=False, warn=False):
    """
    Images should either be locally located in "files" directories or be external links
    """
    if key not in obj:
        assert not force_present, f"{obj_name} object,\n{obj}\n is expected to have {key} image field; none provided!"
        if warn:
            warnings.warn(f"{obj_name} object,\n{obj}\n does not contain image field", UserWarning)
    else:
        assert '://' in obj[key] or obj[key].startswith('files'), \
            f'{obj_name} object,\n{obj}\n image {key}, {obj[key]} should be either an external link or located' \
            f' locally in "files" directory'


def validate_author_data(author):
    """
    Validate author metadata. It should have a name, optionally a list of roles and contact information and image
    """
    assert isinstance(author, dict), \
        f"Author object,\n{author}\n is expected to be a dictionary, got {type(author)} instead!"
    assert 'name' in author, \
        f"Author object,\n{author}\n must contain name field"
    validate_image(author, 'Author')

    roles = author.get('roles', []) + [] if 'role' not in author else [author['role']]
    if not roles:
        warnings.warn(f"No role is specified for author,\n{author}", UserWarning)

    if 'contact' not in author:
        warnings.warn(f"No contact information is specified for author,\n{author}", UserWarning)

    for contact in author.get('contact', []):
        validate_link(contact, 'Contact')


def validate_index(index):
    """
    Validate the index structure and its chapters (which are again of index structure themselves)
    """
    assert isinstance(index, dict), \
        f"Index data,\n{index}\n is supposed to be an object containing [title, description, chapters, ...]"
    # traversing key-values to check descriptors and link lists
    for key, value in index.items():
        if key in ['chapters', ]:
            continue
        # objects should either have descriptors or be a list of link objects
        content = value if isinstance(value, (str, list)) or 'content' not in value else (
            value.get('content', value) if isinstance(value, dict) else value)
        if isinstance(value, dict):
            validate_image(value, key='background')
        if isinstance(content, dict):
            validate_link(content)
        elif isinstance(content, list):
            for link in content:
                validate_link(link)

    for chapter in index.get('chapters', []):
        validate_index(chapter)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Sanity check index.')
    parser.add_argument('--index',
                        dest='index', help='index.yml file path', default=DEFAULT_INDEX_DATA_PATH)
    args = parser.parse_args()
    index_file = read_yaml(args.index)
    validate_index(index_file)
