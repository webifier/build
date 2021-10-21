from dataclasses import dataclass, field
from .io_utils import process_file, save_yaml, read_yaml, data_name, patch_decorator, patch, prepend_baseurl, \
    remove_ending, find_key, process_subs
from .md import build_markdown
from .content import process_content
from .jekyll import create_jekyll_home_header, create_jekyll_file
from .html import process_html
import typing as th
import os
import copy
import jinja2
import functools

SPECIAL_INDEX_KEYS = ['title', 'nav', 'meta', 'config', 'search', 'kind']
SPECIAL_OBJECT_KEYS = ['label', 'kind', 'background', 'style']


@dataclass
class Builder:
    base_url: str
    repo_full_name: str
    output_dir: str = ''
    assets_dir: str = 'assets'
    init_index: tuple = None
    markdown_extensions: th.Optional[th.Iterable[str]] = (
        'md_in_html', 'codehilite', 'fenced_code', 'tables', 'attr_list', 'footnotes', 'def_list')
    checked_indices: set = field(default_factory=set)
    checked_content: dict = field(default_factory=dict)
    search_dict: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    templates_dir: th.Optional[str] = None
    templates_environment = None

    def __post_init__(self):
        if self.templates_dir is not None:
            file_loader = jinja2.FileSystemLoader(self.templates_dir)
            self.templates_environment = jinja2.Environment(loader=file_loader)

    def add_search_content(self, slug, content, title=None, description=None, kind=None):
        slug = remove_ending(slug, [".yml", ".yaml", ".html", ".md"])
        slug = self.init_index[0] if self.init_index[1] == slug else slug
        if slug not in self.search_dict:
            self.add_search_item(slug, slug, title, description, kind)
        self.search_dict[slug]['content'] = set() if 'content' not in self.search_dict[slug] else \
            self.search_dict[slug]['content']
        self.search_dict[slug]['content'].add(content)

    def add_search_item(self, slug, url, title, description=None, kind=None, ):
        slug = remove_ending(slug, [".yml", ".yaml", ".html", ".md"])
        slug = self.init_index[0] if self.init_index[1] == slug else slug
        if slug in self.search_dict:
            return
        result = dict(title=title, url=url)
        result['description'] = description if description else ''
        result['category'] = kind if kind else ''
        self.search_dict[slug] = result

    def save_search_list(self, path=None):
        path = os.path.join(self.output_dir if self.output_dir is not None else '', '_data',
                            'search.yml') if path is None else path
        print('Writing search dict to', path)
        for key in self.search_dict:
            self.search_dict[key]['content'] = " ".join(self.search_dict[key]['content']) \
                if 'content' in self.search_dict[key] else ""
        save_yaml(self.search_dict, path)

    @patch_decorator
    def build_person(self, person, assets_src_dir=None, assets_target_dir=None, search_slug=None):
        assert isinstance(person, dict), \
            f'person objects, are expected to be dictionaries, {type(person)} provided instead!'
        # patching
        for key, value in person.items():
            person[key] = patch(value)

        image = person.get('image', None)
        if search_slug is not None and 'name' in person:
            self.add_search_content(search_slug, person['name'])

        # build contact links
        for idx, contact_info in enumerate(person.get('contact', [])):
            person['contact'][idx] = self.build_link(contact_info, None, add_search_item=False)
            if 'github.com' in contact_info['link']:
                # if no image was provided use person github profile picture instead
                image = f"{contact_info['link']}.png"
        if 'image' in person:
            # copy person's static profile image into assets
            src = person['image'] if assets_src_dir is None else os.path.join(f'{assets_src_dir}', f'{person["image"]}')
            target = person['image'] if assets_target_dir is None else os.path.join(
                f'{assets_target_dir}', f'{person["image"]}')
            image = process_file(src, target, baseurl=self.base_url, base_output_dir=self.output_dir)
        else:
            for contact_info in person.get('contact', []):
                if 'github.com' in contact_info['link']:
                    # if no image was provided use person github profile picture instead
                    image = f"{contact_info['link']}.png"
                    break
        if image:
            person['image'] = image

        # process bio markdown
        if 'bio' in person:
            person['bio'] = build_markdown(builder=self, raw=person['bio'], extensions=self.markdown_extensions)
        return person

    @patch_decorator
    def build_link(self, link, assets_src_dir=None, assets_target_dir=None, search_slug=None, add_search_item=True):
        assets_target_dir = self.assets_dir if assets_target_dir is None else assets_target_dir
        # patching
        for key, value in link.items():
            link[key] = patch(value)
        if 'notebook' in link or 'md' in link:
            link = process_content(builder=self, link=link, kind='notebook' if 'notebook' in link else 'md')
        elif 'index' in link:
            index = self.build_index(index_file=link['index'])
            if 'text' not in link:
                if 'header' in index and 'title' in index['header']:
                    link['text'] = index['header']['title']
                elif 'title' in index:
                    link['text'] = index['title']
            if 'description' not in link and 'header' in index and 'description' in index['header']:
                link['description'] = index['header']['description']
            index_link = remove_ending(link["index"], ['.yml', '.yaml', '.html'])
            link['link'] = prepend_baseurl(index_link if self.init_index[1] != index_link else self.init_index[0],
                                           baseurl=self.base_url)
            link['kind'] = link['kind'] if 'kind' in link else index.get('kind', 'Page')
        elif 'pdf' in link:
            file_path = process_file(link['pdf'], link['pdf'], target_dir='assets', base_output_dir=self.output_dir)
            if file_path:
                link['pdf'] = file_path
            link['kind'] = link['kind'] if 'kind' in link else 'PDF'
            link['link'] = file_path if file_path else link['pdf']
        elif 'kind' in link and link['kind'] == 'person':
            link = self.build_person(link, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
                                     search_slug=search_slug)
        if 'description' in link and 'index' not in link:
            # processing markdown syntax
            link['description'] = build_markdown(builder=self, raw=link['description'],
                                                 extensions=self.markdown_extensions)
        if 'image' in link and not ('kind' in link and link['kind'] == 'person'):
            assert not isinstance(link['image'], dict) or 'src' in link['image'], \
                'no source was specified for link image'
            image_src = link['image']['src'] if isinstance(link['image'], dict) else link['image']

            image_src = process_file(image_src, image_src, src_dir=assets_src_dir, target_dir=assets_target_dir,
                                     baseurl=self.base_url, base_output_dir=self.output_dir)
            if image_src:
                if isinstance(link['image'], dict):
                    link['image']['src'] = image_src
                else:
                    link['image'] = image_src
        # pdf links
        if 'kind' not in link and ('link' in link and link['link'].endswith('.pdf')):
            link['kind'] = 'PDF'
        if add_search_item and ('kind' not in link or link['kind'] != 'person') and (
                'link' in link and not link['link'].startswith('#')):
            self.add_search_item(
                slug=link['link'], url=link['link'], title=link.get('text', link.get('kind', 'External link')),
                description=link.get('description', None), kind=link.get('kind', 'External'))  # todo: add full search

        return link

    @patch_decorator
    def process_template(self, obj, template, template_apply: str = 'whole', template_kind: str = 'jinja2',
                         assets_src_dir=None, assets_target_dir=None, search_slug=None, search_links=False):
        if template_apply == 'value':
            for key, value in obj.items():
                if key in SPECIAL_OBJECT_KEYS:
                    continue
                obj[key] = self.process_template(value, template=template, template_apply='whole',
                                                 template_kind=template_kind, assets_src_dir=assets_src_dir,
                                                 search_links=search_links,
                                                 assets_target_dir=assets_target_dir, search_slug=search_slug)
            result = copy.deepcopy(obj)
        elif template_apply == 'whole':
            # patching object
            for key, value in obj.items():
                obj[key] = patch(value)
            result = {key: value for key, value in obj.items() if key in SPECIAL_OBJECT_KEYS}
            result_content = self.templates_environment.get_template(template).render(
                markdown=functools.partial(build_markdown, builder=self, extensions=self.markdown_extensions,
                                           process_html=False), obj=obj, patch=patch)
            result['content'] = process_html(builder=self, raw_html=result_content, assets_src_dir=assets_src_dir,
                                             assets_target_dir=assets_target_dir, search_links=search_links)
            if search_slug is not None:
                self.add_search_content(slug=search_slug, content=result['content'])
        else:
            raise Exception(f'Template appliance type {template_apply} not available.')
        return result

    @patch_decorator
    def build_object(self, obj, image_key=None, assets_src_dir=None, assets_target_dir=None, search_slug=None,
                     search_links=False):
        """Process the self replicating structure of objects in `index.yml`
        """
        obj = copy.deepcopy(obj)
        assets_target_dir = self.assets_dir if assets_target_dir is None else assets_target_dir
        # building object content
        if isinstance(obj, list):
            # if object is a list of other objects
            for idx, item in enumerate(obj):
                obj[idx] = self.build_link(item, assets_src_dir=assets_src_dir,
                                           assets_target_dir=assets_target_dir, add_search_item=search_links,
                                           search_slug=search_slug)
        elif isinstance(obj, dict):
            template_dict = find_key(obj, query='template', pop=True)
            obj = process_subs(obj, SPECIAL_OBJECT_KEYS + ([image_key] if image_key is not None else []))

            if template_dict:
                obj = self.process_template(obj, template=template_dict.get('template'),
                                            template_apply=template_dict.get('apply', 'whole'),
                                            template_kind=template_dict.get('kind', 'jinja2'),  # todo: add liquid
                                            assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
                                            search_slug=search_slug, search_links=search_links)
            elif 'kind' in obj and obj['kind'] == 'chapters':
                for idx, item in enumerate(obj['content']):
                    obj['content'][idx] = self.build_index(
                        item, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
                        search_slug=search_slug, search_content=search_slug is not None, search_links=search_links)
            else:
                if 'kind' in obj and obj['kind'] == 'people':
                    for item in obj['content']:
                        item['kind'] = 'person'
                for key, value in obj.items():
                    if key in SPECIAL_OBJECT_KEYS + ([image_key] if image_key is not None else []):
                        continue

                    obj[key] = self.build_object(
                        value, image_key, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
                        search_slug=search_slug, search_links=search_links)
        elif isinstance(obj, str):
            content = build_markdown(builder=self, raw=obj, extensions=self.markdown_extensions,
                                     assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir)
            if search_slug:
                self.add_search_content(search_slug, content)
            return content
        else:
            return obj

        # building object (background) image
        if image_key is not None and image_key in obj:
            obj[image_key] = patch(obj[image_key])
            target_path = process_file(obj[image_key], obj[image_key], src_dir=assets_src_dir,
                                       target_dir=assets_target_dir, base_output_dir=self.output_dir,
                                       baseurl=self.base_url)
            if target_path:
                obj[image_key] = target_path
        return obj

    @patch_decorator
    def process_config(self, config: dict):
        # search
        self.config['search'] = dict()
        if 'search' in config and isinstance(config['search'], bool):
            self.config['search']['content'] = config['search']
            self.config['search']['links'] = config['search']
        elif 'search' in config:  # isinstance(config['search'], dict) == True
            self.config['search']['content'] = config['search']['content']
            self.config['search']['links'] = config['search']['links']
        elif 'search' not in config:
            self.config['search']['content'] = True
            self.config['search']['links'] = False
        self.config = {**config, **self.config}
        return self.config

    @patch_decorator
    def build_index(self, index: dict = None, index_file: str = None, assets_src_dir=None, assets_target_dir=None,
                    target_data_file: str = None, index_type='index', search_slug: str = None,
                    search_links: th.Optional[bool] = False, search_content: th.Optional[bool] = False,
                    init_index=False):
        """Process the self replicating structure of `index.yml` and look for notebook links and render them.
        """
        assert index_file is not None or index is not None, f'Either index or index_file should be specified!'
        if index is None:
            index_file = f'{index_file}{"" if index_file.endswith(".yml") or index_file.endswith(".yaml") else ".yml"}'
            search_slug = prepend_baseurl(remove_ending(index_file if target_data_file is None else target_data_file,
                                                        [".yml", ".yaml", ".html", ".md"]), baseurl=self.base_url) if \
                search_slug is None else search_slug
            assert os.path.isfile(index_file), \
                f"{index_type.capitalize()} file {index_file} could not be found!"
            index = read_yaml(index_file)
            if index_file in self.checked_indices:
                index['search'] = self.config['search'] if 'search' not in index else index['search']
                index['kind'] = index.get('kind', index_type.capitalize())
                return index
            print('Processing', index_type, index_file)
            self.checked_indices.add(index_file)

            # processing shared items
            if init_index:
                self.init_index = (
                    remove_ending(index_file if target_data_file is None else target_data_file,
                                  [".yml", ".yaml"]), remove_ending(index_file, [".yml", ".yaml"]))

            return self.build_index(index, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
                                    target_data_file=target_data_file if target_data_file is not None else index_file,
                                    index_type=index_type, init_index=init_index, search_slug=search_slug,
                                    search_links=None, search_content=None)
        assert isinstance(index, dict), \
            f'index is supposed to be an object, got {type(index)}'
        # page info
        if 'title' not in index and 'header' in index and 'title' in index['header']:
            index['title'] = index['header']['title']
        index['title'] = index.get('title', index_type.capitalize())
        index['kind'] = index.get('kind', index_type.capitalize())
        if init_index:
            index['config'] = self.process_config(config=index['config'] if 'config' in index else dict())
        # search config
        if search_links is None and search_content is None:
            index['search'] = self.config['search'] if 'search' not in index else index['search']

            if isinstance(index['search'], bool):
                index['search'] = dict(content=index['search'], links=index['search'])
            search_content = index['search']['content']
            search_links = index['search']['links']
            if index['search']['content'] or index['search']['links']:
                title = index['header']['title'] if 'header' in index and 'title' in index['header'] else \
                    index.get('title', index_type.capitalize())
                description = index.get('header', dict()).get('description', None)
                self.add_search_item(search_slug, search_slug, title=title, description=description,
                                     kind=index.get('kind', index_type.capitalize()))

        # patching special keys
        for key in SPECIAL_INDEX_KEYS:
            if key in index:
                index[key] = patch(index[key])

        if 'nav' in index:
            # process navbar
            if isinstance(index['nav'], dict) and 'brand' in index['nav']:
                index['nav']['brand'] = self.build_link(
                    index['nav']['brand'], assets_src_dir=assets_src_dir,
                    assets_target_dir=assets_target_dir, search_slug=search_slug if search_content else None,
                    add_search_item=search_links)
            else:
                index['nav'] = self.build_object(
                    index['nav'], assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
                    search_slug=search_slug if search_content else None, search_links=search_links)
            if isinstance(index['nav'], dict) and 'content' in index['nav']:
                index['nav']['content'] = self.build_object(
                    index['nav']['content'], assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
                    search_slug=search_slug if search_content else None, search_links=search_links)
            if isinstance(index['nav'], dict) and 'fixed' in index['nav']:
                index['nav']['fixed'] = self.build_object(
                    index['nav']['fixed'], assets_src_dir=assets_src_dir,
                    assets_target_dir=assets_target_dir, search_slug=search_slug if search_content else None,
                    search_links=search_links)

        index = process_subs(index, SPECIAL_INDEX_KEYS + ['header', 'footer'])
        for key, value in index.items():
            if key in SPECIAL_INDEX_KEYS:
                continue
            index[key] = self.build_object(value, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
                                           image_key='background', search_slug=search_slug if search_content else None,
                                           search_links=search_links)

        if index_file is not None or target_data_file is not None:
            # save data file
            print('Saving data:', os.path.join(
                self.output_dir if self.output_dir is not None else '', '_data',
                f'{data_name(index_file if target_data_file is None else target_data_file, index_type)}.yml'))
            save_yaml(
                index, os.path.join(
                    self.output_dir if self.output_dir is not None else '', '_data',
                    f'{data_name(index_file if target_data_file is None else target_data_file, index_type)}.yml')
            )
            # create and save html file
            if index_type == 'index':
                create_jekyll_file(
                    os.path.join(
                        self.output_dir if self.output_dir is not None else '',
                        f'{remove_ending(index_file if target_data_file is None else target_data_file, [".yml", ".yaml"])}.html'
                    ),
                    create_jekyll_home_header(
                        data_name(index_file if target_data_file is None else target_data_file, index_type))
                )
        return index
