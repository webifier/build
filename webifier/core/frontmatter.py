from __future__ import annotations

from typing import Any

import yaml


def split_yaml_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    lines = raw.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, raw

    closing_index = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = i
            break

    if closing_index is None:
        return {}, raw

    metadata = yaml.safe_load("".join(lines[1:closing_index])) or {}
    if not isinstance(metadata, dict):
        raise TypeError("YAML front matter must be a mapping.")
    return metadata, "".join(lines[closing_index + 1 :])
