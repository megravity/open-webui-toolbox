"""Functions and tools: Python sources whose display metadata is derived.

The tracked file is the source itself. `name` is deliberately not stored: it is
a server-side label that may be re-cased independently of the docstring title
(verified on a live instance: 3 of 6 installed functions had a `name` that was
not derivable from their title), and push preserves it rather than applying a
stored copy. `meta` is derived from the docstring by the server, so it is not
stored either (PLAN.md D10); push preserves the server's copy.
"""

import re

from ow.canon import normalize_newlines
from ow.manage.base import Adapter

HEADER_RE = re.compile(r"(?m)^\s*([A-Za-z0-9_.-]+)\s*:\s*(.+?)\s*$")


def header(content):
    """Return the `key: value` lines of a module docstring."""
    parts = content.split('"""')
    if len(parts) < 3:
        raise ValueError("source has no module docstring")
    return dict(HEADER_RE.findall(parts[1]))


class CodeAdapter(Adapter):
    """Shared representation for functions and tools."""

    suffix = ".py"

    def from_file(self, text):
        content = normalize_newlines(text)
        header(content)  # fail early, with a clear message, on a missing header
        return {"content": content}

    def to_file(self, record):
        return record["content"]

    def project(self, record):
        return {"content": record["content"]}


class Functions(CodeAdapter):
    type = "functions"


class Tools(CodeAdapter):
    type = "tools"
