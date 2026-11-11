#!/usr/bin/env python3
"""Preview or apply conservative updates to registered Open WebUI functions."""

import argparse
import ast
from contextlib import nullcontext
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "registry.json"
VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def digest(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def version(content):
    try:
        module = ast.parse(content)
    except SyntaxError as exc:
        raise ValueError("invalid Python source") from exc
    header = ast.get_docstring(module, clean=False) or ""
    values = re.findall(r"(?m)^\s*version\s*:\s*([^\s]+)\s*$", header)
    if len(values) != 1 or not VERSION_RE.fullmatch(values[0]):
        raise ValueError("expected one numeric version in major.minor.patch form")
    return tuple(map(int, values[0].split(".")))


def read_registry_pairs(pairs):
    """Reject duplicate keys; json.loads would silently keep the last value."""
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate keys in registry")
    return dict(pairs)


def read_manifest(path=MANIFEST):
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=read_registry_pairs)
    entries = data.get("functions") if isinstance(data, dict) else None
    if not isinstance(entries, dict) or not entries:
        raise ValueError("registry must contain a non-empty functions map")
    result = []
    for identifier, item_path in entries.items():
        if not isinstance(identifier, str) or not ID_RE.fullmatch(identifier):
            raise ValueError("invalid function ID in registry")
        if not isinstance(item_path, str):
            raise ValueError(f"invalid source path for {identifier}")
        source_path = (ROOT / item_path).resolve()
        if not source_path.is_relative_to(ROOT) or source_path.suffix != ".py":
            raise ValueError(f"invalid source path for {identifier}")
        content = source_path.read_text(encoding="utf-8")
        result.append((identifier, content, version(content)))
    return result


def endpoint(identifier):
    return "/api/v1/functions/id/" + quote(identifier, safe="")


def load_state(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != 1 or not isinstance(data.get("functions"), dict):
        raise ValueError("invalid baseline state file")
    state = data["functions"]
    if any(not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for k, v in state.items()):
        raise ValueError("invalid baseline state entries")
    return state


def save_state(path, state):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".function-sync-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump({"format": 1, "functions": state}, file, indent=2)
            file.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class ApplyLock:
    def __init__(self, path):
        self.path = path
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        self.file = os.fdopen(fd, "a+")
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.file.close()
            raise RuntimeError("another function sync is already applying updates") from None
        return self

    def __exit__(self, *args):
        self.file.close()


def snapshot(function):
    if not isinstance(function, dict) or not isinstance(function.get("content"), str):
        raise ValueError("unexpected function response")
    if not isinstance(function.get("name"), str) or not isinstance(function.get("meta"), dict):
        raise ValueError("missing function name or metadata")
    return tuple(function.get(k) for k in ("id", "name", "type", "content", "meta", "is_active", "is_global", "updated_at"))


def sync(api, entries, state, apply=False, save=None):
    """Return nonzero if a function is blocked or a request fails."""
    failed = False
    installed = api.request("GET", "/api/v1/functions/list")
    if not isinstance(installed, list) or any(not isinstance(f, dict) or not isinstance(f.get("id"), str) for f in installed):
        raise ValueError("unexpected function list response")
    installed_ids = {f["id"] for f in installed}
    registered_ids = {identifier for identifier, _, _ in entries}
    for identifier in sorted(installed_ids - registered_ids):
        print(f"{identifier}: skipped (not registered)")
    for identifier, local, local_version in entries:
        update_attempted = False
        try:
            if identifier not in installed_ids:
                print(f"{identifier}: skipped (not installed)")
                continue
            current = api.request("GET", endpoint(identifier))
            before = snapshot(current)
            if current.get("id") != identifier:
                raise ValueError("function ID mismatch")
            remote_version = version(current["content"])
            remote_hash = digest(current["content"])
            local_hash = digest(local)
            baseline = state.get(identifier)
            if baseline is not None and baseline != remote_hash:
                print(f"{identifier}: conflict (installed source differs from baseline)")
                failed = True
            elif local_hash == remote_hash:
                if baseline is None:
                    if apply:
                        state[identifier] = remote_hash
                        save(state)
                        print(f"{identifier}: in sync; baseline recorded")
                    else:
                        print(f"{identifier}: in sync; run --apply to record baseline")
                else:
                    print(f"{identifier}: in sync")
            elif local_version <= remote_version:
                print(f"{identifier}: skipped (local version is not higher; source differs)")
                failed = True
            elif baseline is None:
                print(f"{identifier}: conflict (no baseline for installed source)")
                failed = True
            elif not apply:
                print(f"{identifier}: update available ({'.'.join(map(str, remote_version))} -> {'.'.join(map(str, local_version))})")
            else:
                fresh = api.request("GET", endpoint(identifier))
                if snapshot(fresh) != before:
                    print(f"{identifier}: conflict (function changed during check)")
                    failed = True
                    continue
                payload = {"id": identifier, "name": current["name"], "meta": current["meta"], "content": local}
                update_attempted = True
                api.request("POST", endpoint(identifier) + "/update", payload)
                verified = api.request("GET", endpoint(identifier))
                snapshot(verified)
                if (verified.get("id") != identifier or verified.get("content") != local
                    or any(verified.get(k) != current.get(k) for k in ("name", "type", "is_active", "is_global"))):
                    print(f"{identifier}: update sent but verification failed; inspect the instance")
                    failed = True
                    continue
                state[identifier] = local_hash
                save(state)
                print(f"{identifier}: updated and verified ({'.'.join(map(str, remote_version))} -> {'.'.join(map(str, local_version))})")
        except (RuntimeError, ValueError, OSError) as exc:
            suffix = "; update may have been applied, inspect the instance" if update_attempted else ""
            print(f"{identifier}: error ({exc}{suffix})")
            failed = True
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="record matching baselines and apply safe updates")
    args = parser.parse_args()
    try:
        sys.path.insert(0, str(ROOT))
        from ow.api import Api
        from ow.client import NoRedirects
        from ow.config import load_config

        url, key = load_config()
        state_root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config").expanduser()
        state_file = state_root / "open-webui-cli" / "function-sync" / (digest(url) + ".json")
        entries = read_manifest()
        api = Api(url, key, NoRedirects())
        lock = ApplyLock(state_file.with_suffix(".lock")) if args.apply else nullcontext()
        with lock:
            state = load_state(state_file)
            return sync(api, entries, state, args.apply, lambda data: save_state(state_file, data))
    except (ImportError, ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
