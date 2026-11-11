"""Models: JSON records that are portable for their own fields only.

A model's `meta` references knowledge collections, files, and avatars by
instance-local ID, so those are excluded from both the tracked file and the
comparison (PLAN.md D9). `is_active` is a toggle and is excluded (D1).
"""

import json

from ow.canon import normalize_newlines
from ow.manage.base import Adapter

STORED_META = ("capabilities", "description")
FIELDS = ("base_model_id", "meta", "name", "params")


def _meta(record):
    meta = record.get("meta") or {}
    return {key: meta[key] for key in STORED_META if key in meta}


def _record(data):
    return {
        "base_model_id": data.get("base_model_id"),
        "meta": _meta(data),
        "name": data.get("name"),
        "params": data.get("params") or {},
    }


class Models(Adapter):
    type = "models"
    suffix = ".json"

    def from_file(self, text):
        data = json.loads(normalize_newlines(text))
        if not isinstance(data, dict):
            raise ValueError("model file must contain a JSON object")
        return _record(data)

    def to_file(self, record):
        return json.dumps(_record(record), indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    def project(self, record):
        return _record(record)
