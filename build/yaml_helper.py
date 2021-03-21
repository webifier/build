from typing import Union, Dict, List, Any
import yaml

YamlNode = Union[Dict[str, 'YamlNode'], List['YamlNode'], str]

def read_yaml(path: str) -> YamlNode:
    with open(path) as file:
        return yaml.full_load(file)
