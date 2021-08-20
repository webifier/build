import typing as th
import shutil
import collections
import yaml
import os
import functools

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


def read_file(path: str) -> str:
    """Read contents of the file and return them as a string"""
    with open(path) as file:
        return file.read()


def save_yaml(data: dict, path: str) -> None:
    """Save input input dictionary as yaml file, creating base directories if necessaries"""
    basedir = '/'.join(path.split('/')[:-1])
    if basedir:
        os.makedirs(basedir, exist_ok=True)
    with open(path, 'w') as outfile:
        yaml.dump(data, outfile, default_flow_style=False)


def prepend_baseurl(url, baseurl=None):
    """Prepend base url to url and remove the redundant [index][.html] ending"""
    prepend = f'/{baseurl}' if baseurl is not None else ''
    result = url if baseurl is None else (f'{prepend}/{url}' if not prepend.endswith(
        '/') else f'{prepend}{url}')
    result = result if result.endswith('.html') else f'{result}.html'
    if baseurl is not None:
        result = result if not result.endswith('index.html') else result.rsplit('index.html', 1)[0]
    return result


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
    return prepend_baseurl(target, baseurl)


def data_name(index_file: str, index_type: str):
    """Generates the file name of yml files with regards to their type"""
    return index_file.replace('.html', '').replace('.yml', '').replace('.yaml', '').replace('/', '_').replace(' ', '')


def patch(obj=None):
    patch_keys = []
    patched = obj
    if obj is not None and isinstance(obj, dict):
        for key in obj:
            if key.startswith('patch'):
                patch_keys.append(key)
        for key in patch_keys:
            patched = patch_with_key(key, patched)
    return patched


def patch_with_key(patch_key, obj=None):
    """Patch object with patch file if any provided"""
    patched = obj
    result = []
    for path in obj[patch_key] if isinstance(obj[patch_key], list) else [obj[patch_key]]:
        if path.endswith('.yml') or path.endswith('.yaml'):
            patch_result = read_yaml(path)
        else:
            patch_result = read_file(path)
        result.append(patch_result)

    if len(obj) > 1 and not isinstance(obj[patch_key], list):
        patched = collections.OrderedDict()
        for key, value in obj.items():
            if key == patch_key:
                if isinstance(result[0], dict):
                    for patched_key, patched_value in result[0].items():
                        patched[patched_key] = patched_value
                else:
                    assert 'content' not in obj, 'cannot patch to existing content'
                    patched['content'] = result[0]
                continue
            patched[key] = value
    elif isinstance(obj[patch_key], list) and isinstance(obj.get('content', None), list):
        idxs = {key: idx for idx, key in enumerate(obj)}
        patched['content'] = result + obj['content'] if idxs[patch_key] < idxs['content'] \
            else obj['content'] + result
        del patched[patch_key]
    elif isinstance(obj[patch_key], list) and len(obj) > 1:
        assert 'content' not in obj, 'cannot patch list to none list content'
        patched['content'] = result
        del patched[patch_key]
    else:
        patched = result if isinstance(obj[patch_key], list) else result[0]
    return patched


def patch_decorator(func):
    """Patch the input object if any patching option were provided"""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        patched = patch(None if not args else args[0])
        if patched is not None:
            return func(self, patched, *args[1:], **kwargs)
        return func(self, *args, **kwargs)

    return wrapper
