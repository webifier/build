import os
from .io_utils import read_file, data_name, prepend_baseurl
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
    content_dir = '/'.join(content.split('/')[:-1]) if os.path.isfile(content) else content # todo: rewrite with os.path
    filename = os.path.join(content_dir, f'index.{"ipynb" if kind == "notebook" else "md"}') if not os.path.isfile(
        content) else content
    if filename in builder.checked_content:
        return builder.checked_content[filename]
    jekyll_target_file = os.path.join(filename.replace(".ipynb" if kind == "notebook" else ".md", '.html'))
    link['link'] = prepend_baseurl(jekyll_target_file, builder.base_url)
    link['kind'] = kind
    # if metadata is not available don't copy it
    metadata_path = link.get('metadata', os.path.join(content_dir, 'metadata.yml'))
    metadata_path = \
        f'{metadata_path}{"" if metadata_path.endswith(".yml") or metadata_path.endswith(".yaml") else ".yml"}'
    if os.path.isfile(metadata_path):
        metadata = builder.build_index(
            index_file=metadata_path.replace(".ipynb" if kind == "notebook" else ".md", ''),
            assets_src_dir=content_dir, assets_target_dir=builder.assets_dir, index_type='content')
        metadata_path = data_name(index_file=metadata_path.replace(".ipynb" if kind == "notebook" else ".md", ''),
                                  index_type='content')
        if 'text' not in link:
            if 'header' in metadata and 'title' in metadata['header']:
                link['text'] = metadata['header']['title']
            elif 'title' in metadata:
                link['text'] = metadata['title']
        if 'description' not in link and 'header' in metadata and 'description' in metadata['header']:
            link['description'] = metadata['header']['description']
    else:
        metadata_path = None
    builder.checked_content[filename] = link
    content = generate_notebook_html(
        builder=builder,
        src=filename,
        assets_dir=builder.assets_dir,  # where to move notebook assets
    ) if kind == 'notebook' else build_markdown(builder, read_file(filename))
    create_jekyll_file(
        target=jekyll_target_file,
        header=create_jekyll_content_header(
            metadata_path=metadata_path,
            colab_url=get_colab_url(content_dir, repo_full_name=builder.repo_full_name) if kind == 'notebook' else None
        ),
        body=content
    )
    return link
