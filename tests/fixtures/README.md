# Synthetic API fixtures

Recordings of Open WebUI API responses, rewritten so every value is invented.
They teach the adapters the real payload *shapes* without carrying anything
from a live instance.

**Nothing here is real.** Identifiers, names, descriptions, prompts, and
schedules are fabricated. Do not treat any value as configuration.

## Garbling rules

| Field | Rule |
| --- | --- |
| UUIDs | Valid v4-shaped `00000000-0000-4000-8000-…` sequence |
| `version_id` | `11111111-1111-4111-8111-<counter>` |
| Emails | `@example.invalid` (RFC 2606 reserved, cannot receive mail) |
| Names, descriptions, prompt text | Obvious placeholders, same rough length |
| Function and tool IDs | `sample_*`, `sample-*` |
| Model IDs | `sample-model*` |
| Timestamps | Fixed epochs (`1700000000`, `1700003600`) so diffs are stable |
| File and knowledge references | `sample-file-*`, `sample-knowledge-base` |

Never add a value copied from a live instance. If a new shape needs a realistic
example, invent one.

## Files

`<type>.list.json` holds a list response; `<type>.one.json` holds the
single-record response for the first item. The two differ in ways the adapters
must respect — list responses carry `content: null` (or omit the field), and
single-record responses add `write_access`.

`models.all.json` is list-only: no single-model endpoint is verified yet.

## Discriminating cases

The fixtures deliberately include the awkward cases:

- `tools.list.json` mixes native Python tools (with `specs`) and tool servers
  (`server:3`, `server:mcp:sample-mcp`) whose `content` is null and which are
  not file-managed.
- `prompts.one.json` has content that starts *and* ends with a newline: the
  byte-exact round-trip requirement (D11) is impossible to test without it.
- `automations.list.json` contains an automation whose name says "Daily" while
  its `rrule` is `FREQ=WEEKLY` — the drift case that motivates automation
  tracking, plus `meta: null` (prompts use `{}` instead).
- `models.all.json` includes instance-local `knowledge`/`voice_avatar`
  references, a model with model controls, and an inactive model.
- Function and tool docstrings mirror `meta.manifest`, which is how the server
  derives metadata (D10).

`tests/test_fixtures.py` enforces these properties, so changing a fixture
without keeping its shape will fail the suite.
