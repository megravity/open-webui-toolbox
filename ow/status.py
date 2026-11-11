"""Read-only three-way comparison of tracked files and instance records.

The comparison is deliberately ordered so that state is never load-bearing for
truth: if the local file and the remote record already agree, the item is in
sync whatever the baseline says. State only answers *who changed first*
(PLAN.md D2).
"""

from collections import Counter
import sys
from typing import NamedTuple

from ow import registry as registry_module
from ow import remote as remote_module
from ow import state as syncstate
from ow.api import Api, HttpError
from ow.config import load_config
from ow.manage import ADAPTERS

IN_SYNC = "in-sync"
PUSH = "push-candidate"
PULL = "pull-candidate"
CONFLICT = "conflict"
UNBASELINED = "unbaselined"
MISSING_LOCAL = "missing-local"
MISSING_REMOTE = "missing-remote"
MOVED = "path-moved"
UNREGISTERED = "remote-unregistered"
INCONSISTENT = "state-inconsistent"
ERROR = "error"

FAILING = (CONFLICT, INCONSISTENT, ERROR)


class Row(NamedTuple):
    type: str
    id: str
    verdict: str
    detail: str = ""


def compare(adapter, text, record, baseline):
    """Return (verdict, detail) for one item."""
    local_eq = adapter.eq_hash(adapter.from_file(text))
    remote_eq = adapter.eq_hash(record)
    if local_eq == remote_eq:
        return IN_SYNC, ""
    if baseline is None:
        return UNBASELINED, "no baseline; run fetch to record one"
    local_changed = adapter.file_hash(text) != baseline["file"]
    remote_changed = remote_eq != baseline["eq"]
    if local_changed and not remote_changed:
        return PUSH, ""
    if remote_changed and not local_changed:
        return PULL, ""
    if local_changed and remote_changed:
        return CONFLICT, "both the file and the instance changed"
    return INCONSISTENT, "baseline matches neither side; re-run fetch"


def adopted_by(adapter, entry):
    """Return a file in the entry's directory carrying the same ID, if any."""
    directory = entry.path.parent
    if not directory.is_dir():
        return None
    for candidate in sorted(directory.glob("*" + adapter.suffix)):
        if candidate == entry.path:
            continue
        try:
            record = adapter.from_file(candidate.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if record.get("id") == entry.id:
            return candidate
    return None


def _row(adapter, type_name, entry, installed, reader, state):
    if not entry.path.exists():
        moved = adopted_by(adapter, entry) if type_name == "prompts" else None
        if moved is not None:
            return Row(type_name, entry.id, MOVED,
                       f"registered path is missing; {moved.name} carries this ID")
        return Row(type_name, entry.id, MISSING_LOCAL, f"tracked file is missing: {entry.path}")
    text = entry.path.read_text(encoding="utf-8")
    if entry.id not in installed:
        return Row(type_name, entry.id, MISSING_REMOTE, "tracked locally but not installed")
    try:
        record = reader.read(type_name, entry.id)
    except HttpError as exc:
        if exc.code == 404:
            return Row(type_name, entry.id, MISSING_REMOTE, "the instance has no such item")
        return Row(type_name, entry.id, ERROR, str(exc))
    except RuntimeError as exc:
        return Row(type_name, entry.id, ERROR, str(exc))
    baseline = syncstate.entry(state, type_name, entry.id) if state else None
    try:
        verdict, detail = compare(adapter, text, record, baseline)
    except ValueError as exc:
        return Row(type_name, entry.id, ERROR, str(exc))
    return Row(type_name, entry.id, verdict, detail)


def collect(registry, reader, state):
    """Return a Row per tracked item, plus one per unregistered installed item."""
    rows = []
    for type_name in sorted(registry):
        adapter = ADAPTERS[type_name]
        entries = registry[type_name]
        try:
            installed = reader.listing(type_name)
        except RuntimeError as exc:
            rows.append(Row(type_name, "*", ERROR, f"could not list: {exc}"))
            continue
        installed = set(installed)
        for identifier, entry in sorted(entries.items()):
            rows.append(_row(adapter, type_name, entry, installed, reader, state))
        for identifier in sorted(installed - set(entries)):
            rows.append(Row(type_name, identifier, UNREGISTERED,
                            "installed but not in the registry"))
    return rows


def render(rows, stream=sys.stdout):
    for row in rows:
        detail = f" ({row.detail})" if row.detail else ""
        print(f"{row.type}/{row.id}: {row.verdict}{detail}", file=stream)
    counts = Counter(row.verdict for row in rows)
    if counts:
        summary = ", ".join(f"{count} {verdict}" for verdict, count in sorted(counts.items()))
        print(f"\n{len(rows)} items: {summary}", file=stream)


def exit_code(rows, check=False):
    failing = [row for row in rows if row.verdict in FAILING]
    if any(row.verdict in (INCONSISTENT, ERROR) for row in failing):
        return 1
    if check and failing:
        return 1
    return 0


def main(types=(), check=False):
    """Report status for the tracked customizations; return an exit code."""
    try:
        if types:
            unknown = set(types) - set(ADAPTERS)
            if unknown:
                raise ValueError(f"unknown customization type: {', '.join(sorted(unknown))}")
        url, key = load_config()
        state_path = registry_module.ROOT / "sync-state.json"
        state = syncstate.load(state_path)
        if state is not None:
            syncstate.check_instance(state, url)
        registry = registry_module.load(types=set(ADAPTERS))
        if types:
            registry = {name: entries for name, entries in registry.items() if name in types}
        rows = collect(registry, remote_module.Remote(Api(url, key)), state)
    except (ImportError, ValueError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    render(rows)
    return exit_code(rows, check)
