import os
import warnings
from yaml_helper import read_yaml

IMAGE_MAX_SIZE = float(os.environ.get('IMAGE_MAX_SIZE', float('inf')))
DEFAULT_INDEX_DATA_PATH = 'index.yml'


def validate_notebook(link):
    notebook_dir = link["notebook"]
    if notebook_dir in checked_notebooks:
        return
    checked_notebooks.add(notebook_dir)

    notebook_file = os.path.join(notebook_dir, 'index.ipynb')
    assert os.path.exists(notebook_file), \
        f"Notebook file {notebook_file}, specified in \n{link}\n could not be found!"

    notebook_metadata_file = os.path.join(notebook_dir, 'metadata.yml')

    if not os.path.exists(notebook_metadata_file):
        warnings.warn(
            f'Notebook metadata file {notebook_metadata_file} specified for {link["notebook"]},'
            f" in \n{link}\n could not be found!", UserWarning)
    else:
        metadata = read_yaml(notebook_metadata_file)
        assert isinstance(metadata, dict), \
            f"Expected metadata file for {notebook_dir}, to be an object containing, {type(metadata)} provided instead!"
        validate_index(metadata)


def validate_link(link, kind=None):
    assert isinstance(link, dict), \
        f"Link object,\n{link}\n is supposed to be object, got {type(link)} instead!"

    if link.get('kind', kind) == 'person':
        validate_person(link)

    media_count = ('link' in link) + ('notebook' in link) + ('pdf' in link) + ('md' in link)
    assert media_count <= 1, \
        f'Link object,\n{link}\n is supposed to have only a single media source, ' \
        f'Link provided instead!'

    if 'notebook' in link and '://' not in link['notebook']:
        # check local notebook links
        validate_notebook(link)

    if 'index' in link:
        assert os.path.isfile(f"{link['index']}.yml"), f'Index file {link["index"]} could not be found!'
        validate_index(read_yaml(f"{link['index']}.yml"), link['index'])

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


def validate_person(person):
    """
    Validate person metadata. It should have a name, optionally a list of roles and contact information and image
    """
    assert isinstance(person, dict), \
        f"Author object,\n{person}\n is expected to be a dictionary, got {type(person)} instead!"
    assert 'name' in person, \
        f"Author object,\n{person}\n must contain name field"
    validate_image(person, 'Author')

    roles = person.get('roles', []) + [] if 'role' not in person else [person['role']]
    if not roles:
        warnings.warn(f"No role is specified for person,\n{person}", UserWarning)

    if 'contact' not in person:
        warnings.warn(f"No contact information is specified for person,\n{person}", UserWarning)

    for contact in person.get('contact', []):
        validate_link(contact, 'Contact')


def validate_index(index, index_file=None):
    """
    Validate the index structure
    """
    if index_file is not None and index_file in checked_indices:
        return
    checked_indices.add(index_file)
    assert isinstance(index, dict), \
        f"Index data,\n{index}\n is supposed to be an object containing [title, description, chapters, ...]"
    # traversing key-values to check descriptors and link lists
    for key, value in index.items():
        # objects should either have descriptors or be a list of link objects
        content = value if isinstance(value, (str, list)) or 'content' not in value else (
            value.get('content', value) if isinstance(value, dict) else value)

        if isinstance(value, dict):
            # check section background
            validate_image(value, key='background')
        if isinstance(content, dict):
            # check section value as link object
            validate_link(content)
        elif isinstance(content, list):
            for link in content:
                if isinstance(value, dict) and value.get('kind', None) == 'index':
                    # check subsections
                    validate_index(value)
                else:
                    validate_link(
                        link=link,
                        kind='person' if isinstance(value, dict) and value.get('kind', None) == 'people' else None
                    )


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Sanity check index.')
    parser.add_argument('--index',
                        dest='index', help='index.yml file path', default=DEFAULT_INDEX_DATA_PATH)
    args = parser.parse_args()
    checked_indices = set()
    checked_notebooks = set()
    validate_index(read_yaml(args.index), args.index)
