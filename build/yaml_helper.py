import typing as th
import collections, yaml
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
    basedir = '/'.join(path.split('/')[:-1])
    if basedir:
        os.makedirs(basedir, exist_ok=True)
    with open(path, 'w') as outfile:
        yaml.dump(data, outfile, default_flow_style=False)
