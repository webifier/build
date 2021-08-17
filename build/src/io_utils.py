import typing as th
import shutil
import collections
import yaml
import os

YamlNode = th.Union[th.Dict[str, 'YamlNode'], th.List['YamlNode'], str]

# preserve ordering in loading and saving yml
_mapping_tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG


def dict_representer(dumper, data):
    return dumper.represent_mapping(_mapping_tag, data.items())


def dict_constructor(loader, node):
    return collections.OrderedDict(loader.construct_pairs(node))


yaml.add_representer(collections.OrderedDict, dict_representer)
yaml.add_constructor(_mapping_tag, dict_constructor)


def read_yaml(path: str) -> YamlNode:
    with open(path) as file:
        return yaml.full_load(file)


def save_yaml(data: dict, path: str) -> None:
    """Save input input dictionary as yaml file, creating base directories if necessaries"""
    basedir = '/'.join(path.split('/')[:-1])
    if basedir:
        os.makedirs(basedir, exist_ok=True)
    with open(path, 'w') as outfile:
        yaml.dump(data, outfile, default_flow_style=False)


def process_file(
        src: str,
        target: str,
        src_dir: th.Optional[str] = None,
        target_dir: th.Optional[str] = None,
        baseurl: th.Optional[str] = None
):
    """
    Process file and move it to target dir only if it is located locally. Returns new path upon move.
    """
    if '://' in src:
        return False
    base_dir = '/'.join(target.split('/')[:-1])
    target_dir = '' if not target_dir else (target_dir if target_dir.endswith('/') else f'{target_dir}/')
    src = src if not src_dir else (f'{src_dir}{src}' if src_dir.endswith('/') else f'{src_dir}/{src}')
    assert os.path.isfile(src), f'{src} file does not exist!'
    if f'{target_dir}{base_dir}':
        os.makedirs(f'{target_dir}{base_dir}', exist_ok=True)
    target = f'{target_dir}{target}'
    shutil.copy2(src, target)
    return target if baseurl is None else (f'{baseurl}/{target}' if not baseurl.endswith(
        '/') else f'{baseurl}{target}')


def data_name(index_file: str, index_type: str):
    """Generates the file name of yml files with regards to their type"""
    return index_file.replace('/', '_').replace(' ', '')
