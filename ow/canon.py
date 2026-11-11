"""Canonical serialization and hashing shared by every adapter."""

import hashlib
import json


def normalize_newlines(text):
    """Return text with CRLF and lone CR converted to LF.

    `file_hash` covers canonical bytes, so a CRLF checkout must not read as a
    local edit on every item (see PLAN.md, D2).
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def canonical_json(value):
    """Serialize deterministically so equal records always hash equally."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(text):
    """Return the sha256 hex digest of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
