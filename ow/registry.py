"""The registry: which customizations this repository manages, and where.

`registry.json` maps a type to item IDs and their tracked file. An entry is
either a path string (the common case) or an object carrying `path` and, for
prompts, the `command` it was registered under. The registry is the only
authority on what is managed; state never adds to it (PLAN.md D2).
"""

import json
from pathlib import Path
from typing import NamedTuple, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "registry.json"


class Entry(NamedTuple):
    type: str
    id: str
    path: Path
    command: Optional[str] = None


def _entry(type_name, identifier, value):
    if not isinstance(identifier, str) or not identifier or "/" in identifier or identifier != identifier.strip():
        raise ValueError(f"invalid {type_name} ID in registry")
    if isinstance(value, str):
        command = None
        raw_path = value
    elif isinstance(value, dict):
        raw_path = value.get("path")
        command = value.get("command")
        unknown = set(value) - {"path", "command"}
        if unknown:
            raise ValueError(f"unknown registry fields for {identifier}: {sorted(unknown)}")
        if command is not None and not isinstance(command, str):
            raise ValueError(f"invalid command for {identifier}")
    else:
        raise ValueError(f"invalid registry entry for {identifier}")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"missing tracked path for {identifier}")
    path = (ROOT / raw_path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"tracked path for {identifier} is outside the repository")
    return Entry(type_name, identifier, path, command)


def load(path=DEFAULT, types=None):
    """Return {type: {id: Entry}} for the registry at path."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("registry must be a JSON object")
    result = {}
    for type_name, entries in data.items():
        if types is not None and type_name not in types:
            raise ValueError(f"unknown customization type in registry: {type_name!r}")
        if not isinstance(entries, dict):
            raise ValueError(f"registry entry for {type_name} must be an object")
        result[type_name] = {identifier: _entry(type_name, identifier, value)
                             for identifier, value in entries.items()}
    return result


def of_type(registry, type_name):
    return registry.get(type_name, {})
