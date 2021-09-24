from dataclasses import dataclass, field
from .io_utils import process_file, save_yaml, read_yaml, data_name, patch_decorator, patch, prepend_baseurl, \
    remove_ending
from .md import build_markdown
from .content import process_content
from .jekyll import create_jekyll_home_header, create_jekyll_file
import typing as th
import os
import copy


@dataclass
class Builder:
    base_url: str
    repo_full_name: str
    assets_dir: str = 'assets'
    markdown_extensions: th.Optional[th.Iterable[str]] = (
        'md_in_html', 'codehilite', 'fenced_code', 'tables', 'attr_list', 'footnotes', 'def_list')
    checked_indices: set = field(default_factory=set)
    checked_content: set = field(default_factory=dict)
    search_dict: list = field(default_factory=dict)

    def add_search_item(self, slug, url, title, description=None, content=None, kind=None, ):
        result = dict(title=title, url=url)
        result['description'] = description if description else ''
        result['content'] = content if content else ''
        result['category'] = kind if kind else ''
        self.search_dict[slug] = result

    def save_search_list(self, path='_data/search.yml'):
        print('Writing search dict to', path)
        save_yaml(self.search_dict, path)

    @patch_decorator
    def build_person(self, person, assets_src_dir=None, assets_target_dir=None):
        assert isinstance(person, dict), \
            f'person objects, are expected to be dictionaries, {type(person)} provided instead!'
        # patching
        for key, value in person.items():
            person[key] = patch(value)

        image = person.get('image', None)

        # build contact links
        for idx, contact_info in enumerate(person.get('contact', [])):
            person['contact'][idx] = self.build_link(contact_info, None, track_search=False)
            if 'github.com' in contact_info['link']:
                # if no image was provided use person github profile picture instead
                image = f"{contact_info['link']}.png"
        if 'image' in person:
            # copy person's static profile image into assets
            src = person['image'] if assets_src_dir is None else f'{assets_src_dir}/{person["image"]}'
            target = person['image'] if assets_target_dir is None else f'{assets_target_dir}/{person["image"]}'
            image = process_file(src, target, baseurl=self.base_url)
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
    def build_link(self, link, assets_src_dir=None, assets_target_dir=None, track_search=True):
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
            link['link'] = prepend_baseurl(link["index"], baseurl=self.base_url)
            link['kind'] = 'Page'
        elif 'pdf' in link:
            file_path = process_file(link['pdf'], link['pdf'], target_dir='assets')
            if file_path:
                link['pdf'] = file_path
            link['link'] = file_path if file_path else link['pdf']
        elif 'kind' in link and link['kind'] == 'person':
            link = self.build_person(link, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir)
        if 'description' in link and 'index' not in link:
            # processing markdown syntax
            link['description'] = build_markdown(builder=self, raw=link['description'],
                                                 extensions=self.markdown_extensions)
        if 'image' in link and not ('kind' in link and link['kind'] == 'person'):
            assert not isinstance(link['image'], dict) or 'src' in link['image'], \
                'no source was specified for link image'
            image_src = link['image']['src'] if isinstance(link['image'], dict) else link['image']

            image_src = process_file(image_src, image_src, src_dir=assets_src_dir, target_dir=assets_target_dir,
                                     baseurl=self.base_url)
            if image_src:
                if isinstance(link['image'], dict):
                    link['image']['src'] = image_src
                else:
                    link['image'] = image_src
        if track_search and ('kind' not in link or link['kind'] != 'person') and not link['link'].startswith('#'):
            if 'kind' not in link and link['link'].endswith('.pdf'):
                link['kind'] = 'PDF'
            self.add_search_item(
                slug=link['link'], url=link['link'], title=link.get('text', link.get('kind', 'External link')),
                description=link.get('description', None), kind=link.get('kind', 'External'))  # todo: add full search

        return link

    @patch_decorator
    def build_object(self, obj, image_key=None, assets_src_dir=None, assets_target_dir=None):
        """Process the self replicating structure of objects in `index.yml`
        """
        obj = copy.deepcopy(obj)
        assets_target_dir = self.assets_dir if assets_target_dir is None else assets_target_dir
        # building object content
        if isinstance(obj, list):
            # if object is a list of other objects
            for idx, item in enumerate(obj):
                obj[idx] = self.build_link(item, assets_src_dir=assets_src_dir,
                                           assets_target_dir=assets_target_dir)
        elif isinstance(obj, dict):
            if 'kind' in obj and obj['kind'] == 'chapters':
                for idx, item in enumerate(obj['content']):
                    obj['content'][idx] = self.build_index(item, assets_src_dir=assets_src_dir,
                                                           assets_target_dir=assets_target_dir)
            else:
                if 'kind' in obj and obj['kind'] == 'people':
                    for item in obj['content']:
                        item['kind'] = 'person'
                for key, value in obj.items():
                    if key in ['label', 'kind'] + [image_key] if image_key is not None else []:
                        continue

                    obj[key] = self.build_object(
                        value, image_key, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir)
        elif isinstance(obj, str):
            return build_markdown(builder=self, raw=obj, extensions=self.markdown_extensions)
        else:
            return obj

        # building object (background) image
        if image_key is not None and image_key in obj:
            obj[image_key] = patch(obj[image_key])
            target_path = process_file(obj[image_key], obj[image_key], src_dir=assets_src_dir,
                                       target_dir=assets_target_dir,
                                       baseurl=self.base_url)
            if target_path:
                obj[image_key] = target_path
        return obj

    @patch_decorator
    def build_index(self, index: dict = None, index_file: str = None, assets_src_dir=None, assets_target_dir=None,
                    target_data_file: str = None, index_type='index'):
        """Process the self replicating structure of `index.yml` and look for notebook links and render them.
        """
        assert index_file is not None or index is not None, f'Either index or index_file should be specified!'
        if index is None:
            index_file = f'{index_file}{"" if index_file.endswith(".yml") or index_file.endswith(".yaml") else ".yml"}'
            assert os.path.isfile(index_file), \
                f"{index_type.capitalize()} file {index_file} could not be found!"
            index = read_yaml(index_file)
            if index_file in self.checked_indices:
                return index
            print(f'Processing {index_type}', index_file)
            self.checked_indices.add(index_file)
            return self.build_index(index, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
                                    target_data_file=target_data_file if target_data_file is not None else index_file,
                                    index_type=index_type)
        assert isinstance(index, dict), \
            f'index is supposed to be an object, got {type(index)}'
        # processing special keys in index
        if 'title' not in index and 'header' in index and 'title' in index['header']:
            index['title'] = index['header']['title']

        # patching special keys
        for key in ['title', 'nav', 'meta', 'config']:
            if key in index:
                index[key] = patch(index[key])
        if 'nav' in index:
            if isinstance(index['nav'], dict) and 'brand' in index['nav']:
                index['nav']['brand'] = self.build_link(index['nav']['brand'], assets_src_dir=assets_src_dir,
                                                        assets_target_dir=assets_target_dir)
            else:
                index['nav'] = self.build_object(index['nav'], assets_src_dir=assets_src_dir,
                                                 assets_target_dir=assets_target_dir)
            if isinstance(index['nav'], dict) and 'content' in index['nav']:
                index['nav']['content'] = self.build_object(index['nav']['content'], assets_src_dir=assets_src_dir,
                                                            assets_target_dir=assets_target_dir)
            if isinstance(index['nav'], dict) and 'fixed' in index['nav']:
                index['nav']['fixed'] = self.build_object(index['nav']['fixed'], assets_src_dir=assets_src_dir,
                                                          assets_target_dir=assets_target_dir)
        index['title'] = index.get('title', index_type.capitalize())
        for key, value in index.items():
            if key in ['title', 'nav', 'meta', 'config']:
                continue
            index[key] = self.build_object(value, assets_src_dir=assets_src_dir, assets_target_dir=assets_target_dir,
                                           image_key='background')

        if index_file is not None or target_data_file is not None:
            # save data file
            save_yaml(
                index,
                f'_data/{data_name(index_file if target_data_file is None else target_data_file, index_type)}.yml'
            )
            # create and save html file
            if index_type == 'index':
                create_jekyll_file(
                    f'{remove_ending(index_file if target_data_file is None else target_data_file, [".yml", ".yaml"])}.html',
                    create_jekyll_home_header(
                        data_name(index_file if target_data_file is None else target_data_file, index_type))
                )
        return index
