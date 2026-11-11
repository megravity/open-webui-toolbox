"""Prompts: markdown with frontmatter carrying identity, and a verbatim body.

The frontmatter holds `id`, `name`, `command`, and `tags`; the path is
conventional but cosmetic, so renaming a command is a file move rather than an
identity change. The body is everything after the closing delimiter minus
exactly one newline, stored verbatim: prompt content is a plain string and may
legitimately begin or end with newlines (PLAN.md D11).

Frontmatter is a strict subset (`key: value` and `[a, b]` lists) parsed with the
standard library only. PyYAML would add a dependency, and `tomllib` requires
Python 3.11 while this project targets 3.9.
"""

from ow.canon import normalize_newlines
from ow.manage.base import Adapter

OPEN = "---\n"
CLOSE = "\n---\n"
FIELDS = ("id", "name", "command", "tags")


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _value(raw):
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [] if not inner else [_unquote(part.strip()) for part in inner.split(",")]
    return _unquote(raw)


def parse(text):
    """Return (frontmatter, body) from a prompt file."""
    text = normalize_newlines(text)
    if not text.startswith(OPEN):
        raise ValueError("prompt file must start with a --- frontmatter block")
    end = text.find(CLOSE, len(OPEN))
    if end < 0:
        raise ValueError("prompt file frontmatter is not closed")
    values = {}
    for line in text[len(OPEN):end].splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        values[key.strip()] = _value(value.strip())
    return values, text[end + len(CLOSE):]


def render(values, body):
    """Return a prompt file from frontmatter values and a verbatim body."""
    tags = values.get("tags") or []
    lines = [OPEN.rstrip("\n")]
    for key in ("id", "name", "command"):
        if values.get(key) is not None:
            lines.append(f"{key}: {values[key]}")
    lines.append("tags: [" + ", ".join(tags) + "]")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


class Prompts(Adapter):
    type = "prompts"
    suffix = ".md"

    def from_file(self, text):
        values, body = parse(text)
        return {"id": values.get("id"), "name": values.get("name"),
                "command": values.get("command"), "tags": values.get("tags") or [],
                "content": body}

    def to_file(self, record):
        return render(record, record["content"])

    def project(self, record):
        # `id` is identity that never changes; `content` already covers it.
        return {"name": record.get("name"), "command": record.get("command"),
                "tags": record.get("tags") or [], "content": record["content"]}
