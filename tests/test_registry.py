"""Registry loading and validation."""

import json
from pathlib import Path
import tempfile
import unittest

from ow import registry


class RegistryTests(unittest.TestCase):
    def load(self, data, types=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return registry.load(path, types=types)

    def test_string_entry(self):
        loaded = self.load({"functions": {"daily": "filters/publish-daily-check-in/filter.py"}})
        entry = loaded["functions"]["daily"]
        self.assertEqual(entry.id, "daily")
        self.assertEqual(entry.command, None)
        self.assertTrue(entry.path.name == "filter.py")

    def test_object_entry_carries_the_command(self):
        loaded = self.load({"prompts": {"abc": {"command": "do-thing", "path": "customizations/prompts/do-thing.md"}}})
        self.assertEqual(loaded["prompts"]["abc"].command, "do-thing")

    def test_unknown_entry_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            self.load({"prompts": {"abc": {"path": "x.md", "nope": 1}}})

    def test_invalid_ids_are_rejected(self):
        for identifier in ("", "a/b", " spaced"):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.load({"functions": {identifier: "filters/x.py"}})

    def test_non_string_id_is_rejected(self):
        # JSON turns object keys into strings, so exercise the validator directly.
        with self.assertRaises(ValueError):
            registry._entry("functions", 7, "filters/x.py")

    def test_paths_outside_the_repository_are_rejected(self):
        for value in ("../../etc/passwd", "/etc/passwd"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.load({"functions": {"daily": value}})

    def test_non_object_type_map_is_rejected(self):
        with self.assertRaises(ValueError):
            self.load({"functions": ["daily"]})

    def test_registry_must_be_an_object(self):
        with self.assertRaises(ValueError):
            self.load([{"functions": {}}])

    def test_unknown_type_is_rejected_when_types_are_declared(self):
        with self.assertRaises(ValueError):
            self.load({"function": {}}, types={"functions", "prompts"})

    def test_missing_registry_raises(self):
        with self.assertRaises(FileNotFoundError):
            registry.load(Path(tempfile.gettempdir()) / "definitely-missing-registry.json")


if __name__ == "__main__":
    unittest.main()
