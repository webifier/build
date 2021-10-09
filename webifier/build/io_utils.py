import typing as th
import shutil
import collections
import yaml
import os
import functools
import copy
import pathlib

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


def remove_ending(string, ending):
    if isinstance(ending, list):
        for end in ending:
            string = remove_ending(string, end)
        return string
    return string if not string.endswith(ending) else string.rsplit(ending, 1)[0]


def prepend_baseurl(url, baseurl=None, handle_html=True):
    """Prepend base url to url and remove the redundant [index][.html] ending"""
    prepend = f'/{baseurl}' if baseurl is not None else ''
    result = url if baseurl is None else (f'{prepend}/{url}' if not prepend.endswith(
        '/') else f'{prepend}{url}')
    if handle_html:
        result = result if result.endswith('.html') else f'{result}.html'
        if baseurl is not None:
            result = remove_ending(result, 'index.html')
    return result


def process_file(
        src: str,
        target: str,
        src_dir: th.Optional[str] = None,
        target_dir: th.Optional[str] = '',
        baseurl: th.Optional[str] = None,
        base_output_dir: th.Optional[str] = ''
):
    """
    Process file and move it to target dir only if it is located locally. Returns new path upon move.
    """
    if '://' in src or src.startswith('data:'):
        return False
    base_dir = os.path.join(*pathlib.Path(target).parts[:-1]) if pathlib.Path(target).parts[:-1] else ''
    src = src if not src_dir else os.path.join(src_dir, src)
    target_dir = target_dir if target_dir is not None else ''
    base_output_dir = base_output_dir if base_output_dir is not None else ''
    assert os.path.isfile(src), f'{src} file does not exist!'
    if os.path.join(base_output_dir, target_dir, base_dir):
        os.makedirs(os.path.join(base_output_dir, target_dir, base_dir), exist_ok=True)
    target = os.path.join(target_dir, target)
    shutil.copy2(src, os.path.join(base_output_dir, target))
    return prepend_baseurl(target, baseurl, handle_html=False)


def data_name(index_file: str, index_type: str):
    """Generates the file name of yml files with regards to their type"""
    return "_".join(pathlib.Path(index_file).parts).replace('.html', '').replace('.yml', '').replace(
        '.yaml', '').replace(' ', '')


def patch(obj=None):
    patched = obj
    if obj is not None and isinstance(obj, dict):
        patch_keys = [key for key in obj if key.startswith('patch')]
        while patch_keys:
            key = patch_keys[0]
            patched = patch_with_key(key, patched)
            patch_keys = [key for key in patched if key.startswith('patch')] if isinstance(patched, dict) else []
    return patched


def patch_with_key(patch_key, obj=None):
    """Patch object with patch file if any provided"""
    patched = copy.deepcopy(obj)
    result = []
    for path in patched[patch_key] if isinstance(patched[patch_key], list) else [patched[patch_key]]:
        if path.endswith('.yml') or path.endswith('.yaml'):
            patch_result = read_yaml(path)
        else:
            patch_result = read_file(path)
        result.append(patch_result)

    if len(obj) > 1 and not isinstance(obj[patch_key], list):
        patched = collections.OrderedDict()
        for key, value in copy.deepcopy(obj).items():
            if key == patch_key:
                if isinstance(result[0], dict):
                    for patched_key, patched_value in result[0].items():
                        patched[patched_key] = patched_value

                else:
                    assert 'content' not in obj, f'cannot patch to existing content, {obj}'
                    patched['content'] = result[0]
                continue
            patched[key] = value
    elif isinstance(obj[patch_key], list) and isinstance(obj.get('content', None), list):
        idxs = {key: idx for idx, key in enumerate(obj)}
        patched['content'] = result + copy.deepcopy(obj['content']) if idxs[patch_key] < idxs['content'] \
            else copy.deepcopy(obj['content']) + result
        del patched[patch_key]
    elif isinstance(obj[patch_key], list) and ('content' not in obj or isinstance(obj['content'], list)):
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


def mix_folders(root_src_dir, root_target_dir, file_map=None):
    if root_src_dir == root_target_dir:
        return
    for src_dir, dirs, files in os.walk(root_src_dir):
        dst_dir = src_dir.replace(root_src_dir, root_target_dir, 1)
        if file_map and root_src_dir != src_dir and os.path.split(src_dir)[1] not in file_map:
            continue
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        for file_ in files:
            if file_map and root_src_dir == src_dir and os.path.split(file_)[1] not in file_map:
                continue
            src_file = os.path.join(src_dir, file_)
            dst_file = os.path.join(dst_dir, file_)
            if not os.path.exists(dst_file):
                shutil.copy(src_file, dst_dir)


def find_key(obj: dict, query: str, pop: bool = False):
    result = dict() if query not in obj else (
        copy.deepcopy(getattr(obj, 'pop' if pop else 'get')(query)) if isinstance(obj[query], dict) else {
            query: copy.deepcopy(getattr(obj, 'pop' if pop else 'get')(query))})
    to_remove = []
    for key in obj:
        if key.startswith(f'{query}-'):
            tag = "-".join(key.split('-')[1:])
            result[tag if tag else query] = obj.get(key)
            if pop:
                to_remove.append(key)
    for key in to_remove:
        obj.pop(key)
    return result


def mix_sub(sub, item, value):
    if item == 'label':
        old_label = sub.get(item, dict())
        if isinstance(old_label, bool):
            return sub
        if isinstance(value, dict):
            sub[item] = {**value, **old_label} if isinstance(old_label, dict) else {**value, "text": old_label}
        elif isinstance(value, str):
            sub[item] = {"text": value, **old_label} if isinstance(old_label, dict) else old_label
        else:
            sub[item] = sub.get(item, value)
    else:
        sub[item] = sub.get(item, value)
    return sub


def process_subs(obj, special_keys):
    subs = find_key(obj, 'sub', pop=True)
    if subs and (len(subs) > 1 or 'apply' not in subs):
        for key in (i for i in obj if i not in special_keys):
            obj[key] = obj[key] if isinstance(obj[key], dict) else dict(content=obj[key])
            for item in [i for i in subs if i != 'apply']:
                if subs.get('apply', 'ignore') == 'ignore':
                    obj[key][item] = obj[key].get(item, subs[item])
                elif subs.get('apply', 'ignore') == 'replace':
                    obj[key][item] = subs[item]
                elif subs.get('apply', 'ignore') == 'mix':
                    obj[key] = mix_sub(obj[key], item, subs[item])
                else:
                    raise Exception(f'Subs apply type {subs["apply"]} is not available')
    return obj
