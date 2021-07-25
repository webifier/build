from sys import argv
import re
from yaml_helper import read_yaml


def check_file(changed_file: str, allowed_files) -> bool:
    for allowed_file in allowed_files:
        if re.match(allowed_file, changed_file):
            return True
    return False


if __name__ == '__main__':
    changed_files = argv[1:]
    allowed_files = read_yaml('build/acceptable-files.yml')

    for changed_file in changed_files:
        assert check_file(changed_file, allowed_files), \
            f"You are not allowed to add, modify or remove file {changed_file}"
