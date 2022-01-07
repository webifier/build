import os
import pathlib
from .io_utils import read_file, data_name, prepend_baseurl, read_yaml
import yaml
from .jekyll import create_jekyll_file, create_jekyll_content_header, get_colab_url
from .notebook import generate_notebook_html
from .md import build_markdown


def process_content(builder, link, kind):
    """Process content link object and generate the pointed content file

    Arguments:
        builder -- the calling builder object
        link {dict} -- pointing link object
        content {str} -- either md or notebook

    Return:
        Processed link object (now holding description and other information of the md and a static link)
    """
    content = link[kind]  # path to content `{folder_name}`
    content_dir = (
        os.path.join(*pathlib.Path(content).parts[:-1]) if pathlib.Path(content).parts[:-1] else '') if os.path.isfile(
        content) else content
    filename = os.path.join(content_dir, f'index.{"ipynb" if kind == "notebook" else "md"}') if not os.path.isfile(
        content) else content
    if filename in builder.checked_content:
        return builder.checked_content[filename]
    jekyll_target_file = os.path.join(filename.replace(".ipynb" if kind == "notebook" else ".md", '.html'))
    link['link'] = prepend_baseurl(jekyll_target_file, builder.base_url)
    # if metadata is not available don't copy it
    metadata_path = link.get('metadata', os.path.join(content_dir, 'metadata.yml'))
    metadata_path = \
        f'{metadata_path}{"" if metadata_path.endswith(".yml") or metadata_path.endswith(".yaml") else ".yml"}'

    metadata = None
    if kind == 'md':
        raw_str = read_file(filename)
        lines = raw_str.splitlines()
        if lines[0] == '---':
            try:
                idx = lines.index('---', 1)
                metadata = yaml.full_load('\n'.join(lines[1:idx]))
                raw_str = '\n'.join(lines[idx + 1:])
            except ValueError:
                pass
        content_str = build_markdown(builder=builder, raw=raw_str, assets_src_dir=content_dir,
                                     assets_target_dir=builder.assets_dir)
    if os.path.isfile(metadata_path):
        file_metadata = builder.build_index(
            index_file=metadata_path.replace(".ipynb" if kind == "notebook" else ".md", ''),
            assets_src_dir=content_dir, assets_target_dir=builder.assets_dir, index_type='content',
            search_slug=jekyll_target_file)
        metadata = file_metadata if metadata is None else {**metadata, **file_metadata}
        metadata_path = data_name(index_file=metadata_path.replace(".ipynb" if kind == "notebook" else ".md", ''),
                                  index_type='content')
        if 'text' not in link:
            if 'header' in metadata and 'title' in metadata['header']:
                link['text'] = metadata['header']['title']
            else:
                link['text'] = metadata.get('title', kind.capitalize())
        if 'description' not in link and 'header' in metadata and 'description' in metadata['header']:
            link['description'] = metadata['header']['description']

    else:
        metadata_path = None if metadata is None else data_name(index_file=metadata_path.replace(
            ".ipynb" if kind == "notebook" else ".md", ''), index_type='content')
        metadata = dict(search=builder.config['search']) if metadata is None else builder.build_index(
            index=metadata, target_data_file=metadata_path.replace(".ipynb" if kind == "notebook" else ".md", ''),
            assets_src_dir=content_dir, assets_target_dir=builder.assets_dir, index_type='content',
            search_slug=jekyll_target_file, search_links=None, search_content=None)

    link['kind'] = metadata.get('kind', kind.capitalize()) if 'kind' not in link else link['kind']

    builder.checked_content[filename] = link
    if kind == 'notebook':
        content_str = generate_notebook_html(
            builder=builder,
            src=filename,
            assets_dir=builder.assets_dir,  # where to move notebook assets
            search_links=metadata['search']['links']
        )

    if metadata['search']['content']:
        builder.add_search_content(
            jekyll_target_file, content=content_str, title=link.get('text', kind.capitalize()),
            kind=link.get('kind', kind.capitalize()), description=link.get('description')
        )
    create_jekyll_file(
        target=os.path.join(
            builder.output_dir if builder.output_dir is not None else '', jekyll_target_file),
        header=create_jekyll_content_header(
            metadata_path=metadata_path,
            colab_url=get_colab_url(content_dir, repo_full_name=builder.repo_full_name) if kind == 'notebook' else None
        ),
        body=content_str
    )
    return link
