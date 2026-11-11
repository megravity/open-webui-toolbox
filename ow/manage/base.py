"""Adapter contract shared by every customization type.

An adapter answers three questions about one type:

- what does the tracked file contain (`from_file` / `to_file`),
- which fields does a push actually control (`project`),
- and therefore do local and remote agree (`eq_hash`)?

`file_hash` covers the canonical rendering, so reformatting a file is not a
change; `eq_hash` covers only projected fields, so a UI toggle is not a change
either (PLAN.md D1).
"""

from ow.canon import canonical_json, digest


class Adapter:
    """Base class for per-type file and record conversions."""

    type = ""
    suffix = ""

    def from_file(self, text):
        """Parse the tracked file into a record."""
        raise NotImplementedError

    def to_file(self, record):
        """Render a record as the canonical tracked file."""
        raise NotImplementedError

    def project(self, record):
        """Return exactly the fields a push controls, and nothing else."""
        raise NotImplementedError

    def eq_hash(self, record):
        """Hash the projected fields, for local/remote comparison."""
        return digest(canonical_json(self.project(record)))

    def file_hash(self, text):
        """Hash the canonical rendering of a tracked file."""
        return digest(self.to_file(self.from_file(text)))
