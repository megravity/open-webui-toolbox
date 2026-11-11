"""Skills: markdown documents that carry their own frontmatter.

The tracked file is the SKILL.md body exactly as the server stores it, already
wrapped in its own `---` frontmatter. Attachment files are a later slice; until
then a skill is tracked as one document, and the file-set fingerprint (D5) is
not yet recorded.
"""

from ow.canon import normalize_newlines
from ow.manage.base import Adapter


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
