"""Guard the synthetic API fixtures.

These tests keep `tests/fixtures/` honest: they check that the fixtures still
mirror the real API shapes the adapters must handle, and that nothing from the
source instance leaked into them. See `fixtures/README.md` for the contract.
"""

import json
import re
from pathlib import Path
import unittest

FIXTURES = Path(__file__).with_name("fixtures")

# Identifiers from the source instance that must never appear in fixtures.
LEAKS = ("gmail", "Marvin", "Deutz", "a6d4b592", "deu.tz", "Classic298",
         "mistral", "deepseek", "opencode", "craft")


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def docstring_fields(content):
    """Extract `key: value` lines from a module docstring header."""
    header = content.split('"""')[1] if content.count('"""') >= 2 else ""
    return dict(match.groups() for match in
                re.finditer(r"(?m)^\s*([a-z_]+)\s*:\s*(.+?)\s*$", header))


class FixtureTests(unittest.TestCase):
    def test_every_fixture_parses(self):
        files = sorted(FIXTURES.glob("*.json"))
        self.assertTrue(files, "no fixtures found")
        for path in files:
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))

    def test_no_source_identifiers_leak(self):
        for path in FIXTURES.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            for leak in LEAKS:
                with self.subTest(path=path.name, leak=leak):
                    self.assertNotIn(leak, text)

    def test_list_responses_omit_content_and_ones_include_it(self):
        for kind in ("functions", "tools"):
            with self.subTest(kind=kind):
                listed = load(f"{kind}.list.json")[0]
                single = load(f"{kind}.one.json")
                self.assertNotIsInstance(listed.get("content"), str)
                self.assertIsInstance(single.get("content"), str)
                self.assertEqual(single["id"], listed["id"])

    def test_tools_mix_native_tools_and_tool_servers(self):
        tools = load("tools.list.json")
        ids = [tool["id"] for tool in tools]
        self.assertTrue(any(ident.startswith("server:mcp:") for ident in ids))
        self.assertTrue(any(not ident.startswith("server:") for ident in ids))
        servers = [tool for tool in tools if tool["id"].startswith("server:")]
        self.assertTrue(all(tool["content"] is None for tool in servers))

    def test_meta_nullability_differs_by_type(self):
        self.assertIsNone(load("automations.list.json")["items"][0]["meta"])
        self.assertEqual(load("prompts.list.json")[0]["meta"], {})

    def test_prompt_content_round_trips_byte_exactly(self):
        # D11: leading and trailing newlines are content, not formatting.
        prompt = load("prompts.one.json")
        self.assertTrue(prompt["content"].startswith("\n"))
        self.assertTrue(prompt["content"].endswith("\n"))
        self.assertEqual(json.loads(json.dumps(prompt["content"])), prompt["content"])

    def test_version_id_present_except_for_automations(self):
        for kind, payload in (("functions", load("functions.one.json")),
                              ("tools", load("tools.one.json")),
                              ("prompts", load("prompts.one.json")),
                              ("skills", load("skills.one.json")),
                              ("models", load("models.all.json")[0])):
            with self.subTest(kind=kind):
                self.assertIsInstance(payload["version_id"], str)
        self.assertNotIn("version_id", load("automations.one.json"))

    def test_meta_manifest_mirrors_the_docstring(self):
        # D10: meta is derived from the docstring, so the fixtures must show it.
        for kind in ("functions", "tools"):
            with self.subTest(kind=kind):
                record = load(f"{kind}.one.json")
                derived = docstring_fields(record["content"])
                manifest = record["meta"]["manifest"]
                self.assertEqual(record["meta"]["description"], derived["description"])
                for key in ("title", "description", "version"):
                    self.assertEqual(manifest[key], derived[key])

    def test_skills_carry_their_own_frontmatter(self):
        content = load("skills.one.json")["content"]
        self.assertTrue(content.startswith("---\n"))
        self.assertIn("\n---\n", content)

    def test_automation_fixture_preserves_the_drift_case(self):
        daily, weekly = load("automations.list.json")["items"]
        self.assertIn("FREQ=DAILY", daily["data"]["rrule"])
        self.assertIn("WEEKLY", weekly["data"]["rrule"])
        self.assertIn("Daily", weekly["name"])  # name disagrees with rrule
        self.assertEqual(weekly["data"]["model_id"], "sample-model-two")

    def test_models_cover_instance_local_references_and_inactive_flag(self):
        models = load("models.all.json")
        self.assertTrue(any((model["meta"] or {}).get("knowledge") for model in models))
        self.assertTrue(any(not model["is_active"] for model in models))


if __name__ == "__main__":
    unittest.main()
