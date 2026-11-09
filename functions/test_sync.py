import copy
import importlib.util
import json
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


class RegistryTests(unittest.TestCase):
    def read(self, functions):
        """Read a registry constructed around the given functions value."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps({"functions": functions}), encoding="utf-8")
            return sync.read_manifest(path)

    def read_raw(self, text):
        """Read a registry from exact text (duplicate keys stay distinct)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(text, encoding="utf-8")
            return sync.read_manifest(path)

    def test_valid_registry_maps_id_to_path_with_version(self):
        with tempfile.TemporaryDirectory(dir=sync.ROOT) as directory:
            module = Path(directory) / "f.py"
            module.write_text(source("1.0.0"), encoding="utf-8")
            relative = module.relative_to(sync.ROOT).as_posix()
            self.assertEqual(self.read({"daily": relative}),
                             [("daily", source("1.0.0"), (1, 0, 0))])

    def test_registry_rejects_list_format(self):
        with self.assertRaises(ValueError) as context:
            self.read([{"id": "daily", "path": "x.py"}])
        self.assertIn("non-empty functions map", str(context.exception))

    def test_registry_rejects_bad_id(self):
        with self.assertRaises(ValueError) as context:
            self.read({"Bad-ID": "x.py"})
        self.assertIn("invalid function ID", str(context.exception))

    def test_registry_rejects_duplicate_ids(self):
        with self.assertRaises(ValueError) as context:
            self.read_raw('{"functions": {"daily": "x.py", "daily": "y.py"}}')
        self.assertIn("duplicate", str(context.exception))

    def test_registry_rejects_paths_outside_repo(self):
        for value in ("/etc/hosts.py", "../evil.py"):
            with self.subTest(value=value), self.assertRaises(ValueError) as context:
                self.read({"daily": value})
            self.assertIn("invalid source path", str(context.exception))

    def test_registry_rejects_non_python_source_suffix(self):
        with self.assertRaises(ValueError) as context:
            self.read({"daily": "not-source.sh"})
        self.assertIn("invalid source path", str(context.exception))

    def test_registry_rejects_missing_source_file(self):
        with self.assertRaises(FileNotFoundError):
            self.read({"daily": "missing_test_target.py"})

    def test_registry_rejects_non_object(self):
        with self.assertRaises(ValueError) as context:
            self.read_raw("[]")
        self.assertIn("non-empty functions map", str(context.exception))

if __name__ == "__main__":
    unittest.main()
