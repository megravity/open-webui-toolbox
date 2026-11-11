"""Adapter behaviour, driven by the synthetic fixtures.

The load-bearing test is `test_ignored_fields_do_not_change_eq`: for every type,
mutating a server-owned or live-only field must leave the comparison hash
alone. Without it, a UI toggle would read as upstream drift forever (D1).
"""

import copy
import json
from pathlib import Path
import unittest

from ow.manage import ADAPTERS
from ow.manage import prompts

FIXTURES = Path(__file__).with_name("fixtures")


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def mutate(record, path, value):
    """Return a deep copy of record with a dotted path replaced."""
    data = copy.deepcopy(record)
    target = data
    keys = path.split(".")
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    return data


# One representative remote record per type.
def remote(kind):
    if kind == "models":
        return load("models.all.json")[0]
    return load(f"{kind}.one.json")


KINDS = ("functions", "tools", "models", "prompts", "skills", "automations")

# Fields a push never applies, or that the server owns. Changing them must not
# make an item look dirty.
IGNORED = {
    "functions": ("is_active", "is_global", "created_at", "updated_at", "user",
                  "user_id", "version_id", "meta", "meta.toggle", "meta.manifest"),
    "tools": ("is_active", "created_at", "updated_at", "user", "user_id",
              "version_id", "specs", "has_user_valves", "access_grants",
              "meta", "write_access"),
    "models": ("is_active", "created_at", "updated_at", "user_id", "version_id",
               "access_grants", "meta.knowledge", "meta.voice_avatar", "meta.voice",
               "meta.background_image_url", "meta.profile_image_url", "meta.i18n",
               "meta.subagents"),
    "prompts": ("is_active", "created_at", "updated_at", "user_id", "version_id",
                "access_grants", "data", "meta", "write_access"),
    "skills": ("is_active", "created_at", "updated_at", "user", "user_id",
               "version_id", "access_grants", "meta", "write_access"),
    "automations": ("is_active", "created_at", "updated_at", "user_id",
                    "next_run_at", "next_runs", "last_run", "last_run_at",
                    "folder_id", "meta"),
}

# Fields a push does apply: changing them must change the hash.
CONTROLLED = {
    "functions": ("content",),
    "tools": ("content",),
    "models": ("name", "params", "base_model_id", "meta.description"),
    "prompts": ("name", "command", "content", "tags"),
    "skills": ("content",),
    "automations": ("name", "data.rrule", "data.model_id", "data.prompt", "data.target"),
}


class AdapterTests(unittest.TestCase):
    def test_every_type_has_an_adapter_and_a_fixture(self):
        self.assertEqual(set(ADAPTERS), set(KINDS))
        for kind in KINDS:
            with self.subTest(kind=kind):
                ADAPTERS[kind].suffix

    def test_rendering_round_trips(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                adapter = ADAPTERS[kind]
                first = adapter.to_file(remote(kind))
                self.assertEqual(adapter.to_file(adapter.from_file(first)), first)

    def test_local_file_and_remote_record_agree(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                adapter = ADAPTERS[kind]
                local = adapter.from_file(adapter.to_file(remote(kind)))
                self.assertEqual(adapter.eq_hash(local), adapter.eq_hash(remote(kind)))

    def test_ignored_fields_do_not_change_eq(self):
        for kind in KINDS:
            adapter = ADAPTERS[kind]
            base = adapter.eq_hash(remote(kind))
            for path in IGNORED[kind]:
                with self.subTest(kind=kind, field=path):
                    changed = mutate(remote(kind), path, {"mutated": True})
                    self.assertEqual(adapter.eq_hash(changed), base)

    def test_controlled_fields_change_eq(self):
        for kind in KINDS:
            adapter = ADAPTERS[kind]
            base = adapter.eq_hash(remote(kind))
            for path in CONTROLLED[kind]:
                with self.subTest(kind=kind, field=path):
                    changed = mutate(remote(kind), path, {"mutated": True})
                    self.assertNotEqual(adapter.eq_hash(changed), base)

    def test_crlf_is_not_a_local_change(self):
        for kind in ("functions", "tools", "skills"):
            with self.subTest(kind=kind):
                adapter = ADAPTERS[kind]
                text = adapter.to_file(remote(kind))
                self.assertEqual(adapter.file_hash(text.replace("\n", "\r\n")),
                                 adapter.file_hash(text))

    def test_reformatting_json_is_not_a_local_change(self):
        for kind in ("models", "automations"):
            with self.subTest(kind=kind):
                adapter = ADAPTERS[kind]
                text = adapter.to_file(remote(kind))
                squashed = json.dumps(json.loads(text), separators=(",", ":"))
                self.assertEqual(adapter.file_hash(squashed), adapter.file_hash(text))

    def test_prompt_body_with_newlines_round_trips_verbatim(self):
        adapter = ADAPTERS["prompts"]
        record = {"id": "p", "name": "Name", "command": "cmd", "tags": ["a", "b"],
                  "content": "\nbody starts after a newline\nand ends with one\n"}
        text = adapter.to_file(record)
        self.assertEqual(adapter.from_file(text), record)
        self.assertEqual(adapter.file_hash(text), adapter.file_hash(
            text.replace("\n", "\r\n")))

    def test_prompt_frontmatter_accepts_quotes_and_lists(self):
        values, body = prompts.parse(
            '---\nid: x\nname: "Quoted Name"\ncommand: c\ntags: [one, "two"]\n---\nbody')
        self.assertEqual(values, {"id": "x", "name": "Quoted Name", "command": "c",
                                  "tags": ["one", "two"]})
        self.assertEqual(body, "body")

    def test_prompt_file_rejects_missing_frontmatter(self):
        with self.assertRaises(ValueError):
            ADAPTERS["prompts"].from_file("just a body\n")
        with self.assertRaises(ValueError):
            ADAPTERS["prompts"].from_file("---\nid: x\n")

    def test_code_file_requires_a_docstring(self):
        with self.assertRaises(ValueError):
            ADAPTERS["functions"].from_file("x = 1\n")

    def test_json_types_reject_non_objects(self):
        for kind in ("models", "automations"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                ADAPTERS[kind].from_file("[1, 2]\n")


if __name__ == "__main__":
    unittest.main()
