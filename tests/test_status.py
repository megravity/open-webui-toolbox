"""The three-way comparison and the status report."""

from pathlib import Path
import tempfile
import unittest

from ow import registry, status
from ow.manage import ADAPTERS


def source(version, extra=""):
    return f'"""\nversion: {version}\n"""\nclass Filter:\n    pass\n{extra}'


def record(content):
    return {"id": "daily", "content": content}


class FakeRemote:
    def __init__(self, installed=None, records=None, error=None):
        self.installed = installed or {}
        self.records = records or {}
        self.error = error

    def listing(self, type_name):
        if self.error:
            raise RuntimeError(self.error)
        return list(self.installed.get(type_name, []))

    def read(self, type_name, identifier):
        return self.records[(type_name, identifier)]


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.adapter = ADAPTERS["functions"]
        self.local = source("1.1.0")
        self.remote = source("1.0.0")

    def baseline(self, text):
        return {"file": self.adapter.file_hash(text),
                "eq": self.adapter.eq_hash(record(text))}

    def test_matching_sides_are_in_sync_without_state(self):
        verdict, _ = status.compare(self.adapter, self.local, record(self.local), None)
        self.assertEqual(verdict, status.IN_SYNC)

    def test_differing_sides_without_state_are_unbaselined(self):
        verdict, detail = status.compare(self.adapter, self.local, record(self.remote), None)
        self.assertEqual(verdict, status.UNBASELINED)
        self.assertIn("fetch", detail)

    def test_local_change_is_a_push_candidate(self):
        verdict, _ = status.compare(self.adapter, self.local, record(self.remote),
                                    self.baseline(self.remote))
        self.assertEqual(verdict, status.PUSH)

    def test_remote_change_is_a_pull_candidate(self):
        verdict, _ = status.compare(self.adapter, self.local, record(self.remote),
                                    self.baseline(self.local))
        self.assertEqual(verdict, status.PULL)

    def test_both_changed_is_a_conflict(self):
        old = source("0.9.0")
        verdict, _ = status.compare(self.adapter, self.local, record(self.remote),
                                    self.baseline(old))
        self.assertEqual(verdict, status.CONFLICT)

    def test_baseline_matching_neither_side_is_inconsistent(self):
        baseline = {"file": self.adapter.file_hash(self.local),
                    "eq": self.adapter.eq_hash(record(self.remote))}
        verdict, _ = status.compare(self.adapter, self.local, record(self.remote), baseline)
        self.assertEqual(verdict, status.INCONSISTENT)

    def test_line_ending_change_is_in_sync(self):
        verdict, _ = status.compare(self.adapter, self.local.replace("\n", "\r\n"),
                                    record(self.local), None)
        self.assertEqual(verdict, status.IN_SYNC)


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def entry(self, type_name, identifier, name, command=None):
        return registry.Entry(type_name, identifier, self.root / name, command)

    def test_missing_tracked_file_is_reported(self):
        rows = status.collect({"functions": {"daily": self.entry("functions", "daily", "nope.py")}},
                              FakeRemote(installed={"functions": ["daily"]}), None)
        self.assertEqual([row.verdict for row in rows], [status.MISSING_LOCAL])

    def test_remote_change_is_reported_per_item(self):
        path = self.root / "f.py"
        path.write_text(source("1.1.0"), encoding="utf-8")
        entry = self.entry("functions", "daily", "f.py")
        rows = status.collect({"functions": {"daily": entry}},
                              FakeRemote(installed={"functions": ["daily"]},
                                         records={("functions", "daily"): record(source("1.0.0"))}),
                              None)
        self.assertEqual(rows[0].verdict, status.UNBASELINED)

    def test_tracked_but_not_installed(self):
        path = self.root / "f.py"
        path.write_text(source("1.0.0"), encoding="utf-8")
        rows = status.collect({"functions": {"daily": self.entry("functions", "daily", "f.py")}},
                              FakeRemote(installed={"functions": []}), None)
        self.assertEqual(rows[0].verdict, status.MISSING_REMOTE)

    def test_unregistered_installed_items_are_listed(self):
        rows = status.collect({"functions": {}},
                              FakeRemote(installed={"functions": ["a", "b"]}), None)
        self.assertEqual({row.id for row in rows}, {"a", "b"})
        self.assertTrue(all(row.verdict == status.UNREGISTERED for row in rows))

    def test_listing_failure_becomes_an_error_row(self):
        rows = status.collect({"functions": {}}, FakeRemote(error="boom"), None)
        self.assertEqual(rows[0].verdict, status.ERROR)
        self.assertIn("boom", rows[0].detail)

    def test_prompt_rename_is_detected_by_frontmatter_id(self):
        prompts = ADAPTERS["prompts"]
        moved = self.root / "current.md"
        moved.write_text(prompts.to_file({"id": "abc", "name": "N", "command": "c",
                                          "tags": [], "content": "body"}), encoding="utf-8")
        entry = self.entry("prompts", "abc", "old.md")
        rows = status.collect({"prompts": {"abc": entry}},
                              FakeRemote(installed={"prompts": ["abc"]}), None)
        self.assertEqual(rows[0].verdict, status.MOVED)
        self.assertIn("current.md", rows[0].detail)


class ExitCodeTests(unittest.TestCase):
    def row(self, verdict):
        return status.Row("functions", "x", verdict)

    def test_in_sync_is_clean(self):
        self.assertEqual(status.exit_code([self.row(status.IN_SYNC)], check=True), 0)

    def test_conflict_only_fails_with_check(self):
        self.assertEqual(status.exit_code([self.row(status.CONFLICT)]), 0)
        self.assertEqual(status.exit_code([self.row(status.CONFLICT)], check=True), 1)

    def test_errors_and_inconsistency_always_fail(self):
        for verdict in (status.ERROR, status.INCONSISTENT):
            with self.subTest(verdict=verdict):
                self.assertEqual(status.exit_code([self.row(verdict)]), 1)


if __name__ == "__main__":
    unittest.main()
