"""Automations: JSON records that drift silently because nothing versions them.

The tracked file holds the authored configuration only. `is_active`,
`next_run_at`, `next_runs`, `last_run`, `last_run_at`, and `folder_id` are
runtime or instance-local and are excluded (PLAN.md D1, D4). `model_id` is
always written explicitly so a push can never re-pin it by omission.
"""

import json

from ow.canon import normalize_newlines
from ow.manage.base import Adapter

FIELDS = ("model_id", "prompt", "rrule", "target", "terminal")


def _data(record):
    data = record.get("data") or {}
    return {key: data.get(key) for key in FIELDS}


def _record(data):
    return {"name": data.get("name"), "data": _data(data)}


class Automations(Adapter):
    type = "automations"
    suffix = ".json"

    def from_file(self, text):
        data = json.loads(normalize_newlines(text))
        if not isinstance(data, dict):
            raise ValueError("automation file must contain a JSON object")
        return _record(data)

    def to_file(self, record):
        return json.dumps(_record(record), indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    def project(self, record):
        return _record(record)
