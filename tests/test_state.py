"""Sync state behaviour: schema, atomic writes, and the no-op guarantee."""

import json
from pathlib import Path
import tempfile
import unittest

from ow import state as syncstate

FORMAT = 1
A = "a" * 64
B = "b" * 64
URL = "http://open-webui.example:3000"


def sample(**entry):
    return {"format": FORMAT, "instance": URL,
            "items": {"functions": {"sample": dict({"file": A, "eq": B}, **entry)}}}


class StateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "nested" / "sync-state.json"

    def test_missing_state_is_none(self):
        self.assertIsNone(syncstate.load(self.path))

    def test_round_trip(self):
        state = sample(version_id="v1")
        self.assertTrue(syncstate.save(self.path, state))
        self.assertEqual(syncstate.load(self.path), state)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_unchanged_state_is_not_rewritten(self):
        state = sample(version_id="v1")
        syncstate.save(self.path, state)
        before = self.path.stat().st_mtime_ns
        self.assertFalse(syncstate.save(self.path, state))
        self.assertEqual(self.path.stat().st_mtime_ns, before)

    def test_render_is_stable_and_ordered(self):
        state = sample(version_id="v1")
        state["items"]["automations"] = {"z": {"file": A, "eq": B}}
        text = syncstate.render(state)
        self.assertTrue(text.endswith("\n"))
        self.assertLess(text.index('"automations"'), text.index('"functions"'))

    def test_invalid_states_are_rejected(self):
        cases = {
            "not an object": [],
            "wrong format": {"format": 2, "instance": URL, "items": {}},
            "missing instance": {"format": FORMAT, "items": {}},
            "bad hash": {"format": FORMAT, "instance": URL,
                         "items": {"functions": {"x": {"file": "nope", "eq": B}}}},
            "missing eq": {"format": FORMAT, "instance": URL,
                           "items": {"functions": {"x": {"file": A}}}},
            "unknown field": {"format": FORMAT, "instance": URL,
                              "items": {"functions": {"x": {"file": A, "eq": B, "path": "x"}}}},
            "bad version_id": {"format": FORMAT, "instance": URL,
                               "items": {"functions": {"x": {"file": A, "eq": B, "version_id": 1}}}},
        }
        for label, state in cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                syncstate.validate(state)

    def test_corrupt_file_is_not_silently_reset(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"format": 99}')
        with self.assertRaises(ValueError):
            syncstate.load(self.path)

    def test_instance_mismatch_is_an_error(self):
        state = sample()
        syncstate.check_instance(state, URL)
        with self.assertRaises(ValueError):
            syncstate.check_instance(state, "http://other.example:3000")

    def test_record_keeps_optional_fields_when_omitted(self):
        state = syncstate.empty(URL)
        syncstate.record(state, "skills", "demo", A, B, version_id="v1", files="c" * 64)
        syncstate.record(state, "skills", "demo", B, A)
        entry = syncstate.entry(state, "skills", "demo")
        self.assertEqual(entry, {"file": B, "eq": A, "version_id": "v1", "files": "c" * 64})

    def test_prune_removes_unregistered_entries(self):
        state = sample()
        state["items"]["models"] = {"gone": {"file": A, "eq": B}}
        removed = syncstate.prune(state, {"functions": ["sample"], "models": []})
        self.assertEqual(removed, [("models", "gone")])
        self.assertNotIn("models", state["items"])
        self.assertEqual(syncstate.entry(state, "functions", "sample")["file"], A)

    def test_rendered_state_has_no_content(self):
        state = sample(version_id="v1")
        text = syncstate.render(state)
        json.loads(text)
        for forbidden in ("content", "secret", "http://open-webui.example:3000/api"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
