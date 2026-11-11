"""Skills: markdown documents that carry their own frontmatter.

The tracked file is the SKILL.md body exactly as the server stores it, already
wrapped in its own `---` frontmatter. A skill may also carry attached files; the
file-set fingerprint below records which ones existed at the last sync, so a
push can refuse to rewrite a skill whose folder has silently narrowed
(PLAN.md D5).
"""

from ow.canon import canonical_json, digest, normalize_newlines
from ow.manage.base import Adapter


def file_set_hash(files):
    """Return a fingerprint of a skill's file set, by path only.

    Replacing a skill rewrites it wholesale, so a file that fetch never
    captured would be deleted on the instance. The guard compares *which* files
    exist, not what they contain: a content edit is not a file-set change, and
    folding sizes in would make every edit look like a removal.
    """
    paths = []
    for entry in files:
        path = entry.get("path") if isinstance(entry, dict) else entry
        if not isinstance(path, str) or not path:
            raise ValueError("skill file entries need a path")
        paths.append(path)
    if len(paths) != len(set(paths)):
        raise ValueError("skill file set contains duplicate paths")
    return digest(canonical_json(sorted(paths)))


class Skills(Adapter):
    type = "skills"
    suffix = ".md"

    def from_file(self, text):
        return {"content": normalize_newlines(text)}

    def to_file(self, record):
        return record["content"]

    def project(self, record):
        # name and description are derived from the document's own frontmatter.
        return {"content": record["content"]}

    def file_set_hash(self, files):
        return file_set_hash(files)
