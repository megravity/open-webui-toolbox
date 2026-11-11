"""Committed sync state: what each tracked item looked like at the last sync.

The file is generated, never authored. It holds hashes, `version_id` tokens,
and the instance URL, and nothing derived from file bodies: no content, no
paths, no timestamps (PLAN.md D2). A write that changes nothing is skipped, so
a no-op run leaves the working tree byte-identical.
"""

import json
import os
from pathlib import Path
import re
import tempfile

FORMAT = 1
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
ENTRY_FIELDS = ("eq", "file", "files", "version_id")


def empty(instance):
    return {"format": FORMAT, "instance": instance, "items": {}}


def validate(state):
    if not isinstance(state, dict):
        raise ValueError("state must be a JSON object")
    if state.get("format") != FORMAT:
        raise ValueError(f"unsupported state format: {state.get('format')!r}")
    instance = state.get("instance")
    if not isinstance(instance, str) or not instance:
        raise ValueError("state must record the instance it belongs to")
    items = state.get("items")
    if not isinstance(items, dict):
        raise ValueError("state items must be a JSON object")
    for type_name, records in items.items():
        if not isinstance(type_name, str) or not type_name:
            raise ValueError("state type names must be non-empty strings")
        if not isinstance(records, dict):
            raise ValueError(f"state for {type_name} must be a JSON object")
        for identifier, entry in records.items():
            if not isinstance(identifier, str) or not identifier:
                raise ValueError(f"invalid state entry ID in {type_name}")
            if not isinstance(entry, dict):
                raise ValueError(f"state entry for {identifier} must be a JSON object")
            unknown = set(entry) - set(ENTRY_FIELDS)
            if unknown:
                raise ValueError(f"unknown state fields for {identifier}: {sorted(unknown)}")
            for field in ("file", "eq", "files"):
                if field in entry and (not isinstance(entry[field], str)
                                       or not HASH_RE.fullmatch(entry[field])):
                    raise ValueError(f"state entry for {identifier} has an invalid {field} hash")
            if not {"file", "eq"} <= set(entry):
                raise ValueError(f"state entry for {identifier} needs file and eq hashes")
            if "version_id" in entry and not isinstance(entry["version_id"], str):
                raise ValueError(f"state entry for {identifier} has an invalid version_id")


def render(state):
    return json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load(path):
    """Return the state at path, or None when it does not exist yet."""
    path = Path(path)
    if not path.exists():
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    validate(state)
    return state


def save(path, state):
    """Write state atomically; return False when nothing changed."""
    path = Path(path)
    validate(state)
    text = render(state)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".sync-state-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(text)
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return True


def check_instance(state, instance):
    """Refuse to compare hashes taken against a different instance."""
    if state.get("instance") != instance:
        raise ValueError(
            f"sync state belongs to {state.get('instance')!r}, not {instance!r}; "
            "run fetch for this instance or remove sync-state.json"
        )


def entry(state, type_name, identifier):
    return (state.get("items", {}).get(type_name) or {}).get(identifier)


def record(state, type_name, identifier, file_hash, eq_hash, version_id=None, files=None):
    """Record a baseline, keeping existing optional fields when omitted."""
    items = state.setdefault("items", {})
    records = items.setdefault(type_name, {})
    current = records.setdefault(identifier, {})
    current["file"] = file_hash
    current["eq"] = eq_hash
    if version_id is not None:
        current["version_id"] = version_id
    if files is not None:
        current["files"] = files
    return current


def prune(state, known):
    """Drop entries for items no longer in the registry.

    `known` maps a type name to the identifiers still tracked, so state never
    becomes a second authority on what is managed (PLAN.md D2).
    """
    removed = []
    items = state.get("items", {})
    for type_name in list(items):
        records = items[type_name]
        keep = set(known.get(type_name, ()))
        for identifier in sorted(set(records) - keep):
            del records[identifier]
            removed.append((type_name, identifier))
        if not records:
            del items[type_name]
    return removed
