import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("function_sync", Path(__file__).with_name("sync.py"))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def source(version, extra=""):
    return f'"""\nversion: {version}\n"""\nclass Filter:\n    pass\n{extra}'


class FakeApi:
    def __init__(self, content):
        self.function = {"id": "daily", "name": "Daily", "type": "filter", "content": content,
                         "meta": {"description": "existing"}, "is_active": True,
                         "is_global": False, "updated_at": 1}
        self.posts = []
        self.gets = 0
        self.concurrent_change = False
        self.fail_after_post = False

    def request(self, method, path, payload=None):
        if path == "/api/v1/functions/list":
            return [{"id": "daily"}]
        if method == "POST":
            self.posts.append(copy.deepcopy(payload))
            self.function["content"] = payload["content"]
            self.function["updated_at"] += 1
            return copy.deepcopy(self.function)
        self.gets += 1
        if self.concurrent_change and self.gets == 2:
            self.function["name"] = "Changed"
        if self.fail_after_post and self.posts:
            raise RuntimeError("unavailable")
        return copy.deepcopy(self.function)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.old = source("1.0.0")
        self.new = source("1.1.0")
        self.entries = [("daily", self.new, sync.version(self.new))]
        self.api = FakeApi(self.old)
        self.state = {"daily": sync.digest(self.old)}
        self.saves = []

    def run_sync(self, apply=False):
        return sync.sync(self.api, self.entries, self.state, apply, lambda state: self.saves.append(dict(state)))

    def test_preview_does_not_write(self):
        self.assertEqual(self.run_sync(), 0)
        self.assertEqual(self.api.posts, [])
        self.assertEqual(self.saves, [])

    def test_apply_preserves_metadata_and_verifies(self):
        self.assertEqual(self.run_sync(True), 0)
        self.assertEqual(self.api.posts[0]["meta"], {"description": "existing"})
        self.assertEqual(self.api.function["content"], self.new)
        self.assertEqual(self.state["daily"], sync.digest(self.new))
        self.assertEqual(self.saves[-1], self.state)

    def test_no_baseline_never_overwrites(self):
        self.state.clear()
        self.assertEqual(self.run_sync(True), 1)
        self.assertEqual(self.api.posts, [])

    def test_installed_edits_conflict(self):
        self.api.function["content"] += '# local edit\n'
        self.assertEqual(self.run_sync(True), 1)
        self.assertEqual(self.api.posts, [])

    def test_simultaneous_edit_stops_update(self):
        self.api.concurrent_change = True
        self.assertEqual(self.run_sync(True), 1)
        self.assertEqual(self.api.posts, [])

    def test_same_version_different_content_does_not_update(self):
        self.api.function["content"] = source("1.1.0", '# different\n')
        self.state["daily"] = sync.digest(self.api.function["content"])
        self.assertEqual(self.run_sync(True), 1)
        self.assertEqual(self.api.posts, [])

    def test_matching_source_baseline_is_opt_in(self):
        self.api.function["content"] = self.new
        self.state.clear()
        self.assertEqual(self.run_sync(), 0)
        self.assertEqual(self.saves, [])
        self.assertEqual(self.run_sync(True), 0)
        self.assertEqual(self.state["daily"], sync.digest(self.new))
        self.assertEqual(self.api.posts, [])

    def test_failed_post_verification_does_not_advance_baseline(self):
        self.api.fail_after_post = True
        self.assertEqual(self.run_sync(True), 1)
        self.assertEqual(self.state["daily"], sync.digest(self.old))
        self.assertEqual(self.saves, [])

    def test_versions_reject_non_numeric_or_missing(self):
        for value in ("1.0.0-rc1", "1.0", "01.0.0", "bad"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                sync.version(source(value))

    def test_state_file_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "state.json"
            sync.save_state(path, self.state)
            self.assertEqual(sync.load_state(path), self.state)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
