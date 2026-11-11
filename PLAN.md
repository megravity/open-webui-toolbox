# PLAN — open-webui-toolbox as the authoritative home for Open WebUI customizations

Status: proposal, revised after an instance-agent review of 2026-11-08 (see
"Design decisions" for what that review changed). Target instance: Open WebUI
0.13.2 (re-verify adapter endpoints against it when building; some facts come
from current upstream `main` and can drift).

## Goal

`open-webui-toolbox` becomes the authoritative home for an instance's
customizations: all customization types tracked in this repo as files, git
history the change log, with a two-way tool (`ow fetch` / `ow status` /
`ow push`) built on one integrated `ow` binary. The raw API client stays
importable underneath management commands.

Boundary statement: "authoritative" applies to each customization's own
fields. Model records reference knowledge bases, files, and tools by
*instance-local IDs*; the repo is authoritative for the model's own fields,
not for what its references point at (see D9).

## Current state

| Component | Path | Role |
| --- | --- | --- |
| Launcher | `cli/ow` | Thin shim over the `ow` package |
| Raw client | `ow/client.py`, `ow/config.py` | `setup`, `get/post/put/patch/delete`, chat/automation shortcuts, pagination, no-redirect policy |
| Function sync | `functions/sync.py` | Conservative local → remote updates from `registry.json` |
| Registry | `registry.json` | `{type: {id: file}}` maps; function sources under `filters/` |
| Visual style | `visual-style/` | Reference assets; not API-managed |

## Verified API surface (per Open WebUI source, 0.13.2 era)

| Type | Shape | Key endpoints |
| --- | --- | --- |
| Functions | Python `content`, `name`, `meta`, `type` (filter/pipe/action), `is_active`, `is_global` | `GET /api/v1/functions/list`, `GET|POST /api/v1/functions/id/{id}[/update]`, `POST /api/v1/functions/create` |
| Tools | Python `content` + server-generated `specs`, `name`, `meta` | `GET /api/v1/tools/`, `GET|POST /api/v1/tools/id/{id}[/update]`, `POST /api/v1/tools/create` |
| Models | Plain JSON: `base_model_id`, `name`, `meta`, `params`, `is_active`, `access_grants`, `commit_message` on update; references KBs/files/tools by instance-local ID | `GET /api/v1/models/all`, `GET /api/v1/models/export?ids=`, `POST /api/v1/models/import` (bulk), `POST /api/v1/models/model/update`, `POST /api/v1/models/create` |
| Prompts | JSON keyed by `id`, `command`, `content`, tags, server-side `version_id` history | `GET /api/v1/prompts/`, `GET|POST /api/v1/prompts/id/{id}[/update]`, `POST /api/v1/prompts/create` |
| Skills | Markdown `content` + attached files (SKILL.md layout), `description`, `meta`, `is_active`, `access_grants`, `version_id`, zip import; `/import` `replace` is a whole-object rewrite | `GET /api/v1/skills/`, `GET /api/v1/skills/id/{id}`, `POST.../update`, `POST /api/v1/skills/create`, `GET /api/v1/skills/export` |
| Automations | Record: schedule config, prompt, `model_id`, activation | `GET /api/v1/automations/list` (paginated `{total, items}`), `GET|POST /api/v1/automations/{id}[/update]`, `DELETE.../delete`; create path: verify on instance |

Common rules: admin-key conventions, per-type access checks (403 on
single-item reads is a report, not a failure). `version_id` exists on
functions, tools, models, prompts, and skills — **not automations** — so four
families get optimistic concurrency and automations fall back to
read-before-write plus re-read. List endpoints omit `content` (absent on
functions, `null` on tools), so any comparison needs one GET per item; the
current instance has 59 items across the six types.

Tools are not one kind: the list mixes native Python tools with tool servers
(`server:3`, `server:mcp:<id>`), which are not file-managed and must be
filtered out and reported.

## Target layout

```
open-webui-toolbox/
  ow/                      # package: client, config, state, manage adapters
  cli/ow                   # launcher shim
  customizations/
    functions/  tools/  models/  prompts/  skills/     # one file per item
    automations/            # promoted from "later" (see D4)
  registry.json            # {type: {id: path}}; prompts store id+command+path
  sync-state.json          # committed sync state (see D2)
```

Commands after integration:

```
ow setup                                   # unchanged
ow status [type...]                        # read-only three-way summary
ow fetch [type...]                         # instance -> files + state
ow push [type...] [--all]                  # gated apply of local files
ow get /api/... [-d ...] [--raw]           # unchanged raw passthrough
```

## Design decisions (recorded with provenance)

Incorporates the instance-agent review of 2026-11-08. Decisions D1–D3 were
that review's top findings; the rest follow from it.

- **D1 — Store what the artifact is; never store what a push would re-apply.**
  The line is not "source vs runtime" as a judgement call. It is: fields
  stored in a committed file are rewritten by `fetch`, so a stored *toggle*
  becomes a `fetch` → `push` cycle that silently reverts an admin's click —
  the same failure class as the `commit_message`/`model_id` re-pin. Stored
  fields are identity and authorship, which push preserves and which the file
  should simply track; discarded fields are toggles and server-derived output.
  - **Stored in the file:** `content`/code, `id`, and `type` (function
    `filter`/`pipe`/`action` — identity, not runtime). `name` is stored for
    record types (models, prompts, automations), where it is part of the JSON
    record the file already owns, but **not** for code types: it is a
    server-side label that is not derived from the docstring title (verified:
    3 of 6 installed functions disagreed) and push preserves it. `meta` is not
    stored at all (see D10).
  - **Stored in the state file, committed — see D2:** `version_id` as an
    optimistic-concurrency token, plus the last-synced remote hash. Dropping
    `version_id` here would silently discard the skills/prompts concurrency
    guard: push needs the version it last saw, which is history, not state of
    the world.
  - **Live only, reported by `status`, never stored:** `is_active`,
    `is_global`, `specs`, timestamps, `user.id`, `access_grants`.
  - **Residual gap, accepted:** the repo no longer describes desired
    activation, so a fresh install on a new instance gets defaults. With two
    instances out of scope for v1 and push preserving the flag, that is the
    correct thing to accept. `access_grants` is in the same bucket and is
    never stored or pushed (revisit at Phase 5, or it will be rediscovered
    then).
  - Automations have no `version_id`, so their push relies on read-before-write
    and re-read rather than a token.
- **D2 — Sync state is committed in the repo.** `version_id` and the
  last-synced hashes are history, not derivable; outside the repo a fresh
  clone reads as all-changed. `sync-state.json` at repo root stores hashes,
  `version_id`, and IDs only. Pairing rule: a change commit always carries its
  state update together (discipline in v1; tool-side `--commit` later).
  Rejected alternatives, with the failure each brings:
  - *Git as the baseline* (`remote ≠ blob at HEAD`) looks equivalent and is
    not: commit an edit without pushing and the next `status` reports remote
    changed when the truth is you are ahead. Every unpushed commit silently
    reclassifies as upstream drift. Repairing it needs a reference blob "at
    the last verified push", which is a recorded fact, not a derivable one —
    the same wall reached from the other side. There is no fresh-clone story
    without committed state: `status` on a clone is either lying or useless.
  - *Derive-from-git history* breaks under amend and rebase.
  - *Expendable external state* degrades to re-fetch plus manual reconcile.
  Single file for now. Per-item state (`sync-state/<type>/<id>.json`) would
  scope conflicts to one item, at the cost of a directory and a larger commit
  surface; it only pays off if you actually branch and push from both sides,
  so it is not pre-paid.

  **State file shape.** One `sync-state.json` at the repo root, generated not
  authored. It holds a `format` version, the instance URL, and per-type maps of
  item ID to `{file, eq, version_id}` (skills add a `files` fingerprint).

  ```json
  {
    "format": 1,
    "instance": "http://open-webui.example:3000",
    "items": {
      "functions": {
        "example_function": {
          "file": "<sha256>",
          "eq": "<sha256>",
          "version_id": "00000000-0000-4000-8000-000000000000"
        }
      }
    }
  }
  ```

  The instance URL is stored in full rather than hashed: it is not a secret,
  and it is what turns the worst silent failure — comparing instance B against
  hashes from instance A — into a hard error instead of a tree full of phantom
  drift.

  **Invariants.** No content, no secrets, no paths (the registry owns paths,
  or that fact has two homes). No timestamps: git records when a state change
  landed, and timestamps in a committed file force a diff on every write.
  Ordered keys and sorted items so diffs read like any other file. A write that
  changes nothing is skipped, so a no-op run leaves the tree byte-identical.
  Missing state is not corruption (see below); invalid state is a loud error,
  never a silent reset.

  **Hash definitions.** `file` is sha256 over canonical bytes — exactly what
  the adapter renders from its parsed representation — so a reindent or key
  reorder is not a change. Adapters also normalize CRLF to LF on read, so a
  CRLF checkout is not a change either; `.gitattributes` with
  `* text=auto eol=lf` is worth adding for clean diffs but is not load-bearing.
  `eq` is sha256 over canonical JSON of the adapter's projection, emitting
  every controlled key always; absent collapses to `null` but `null` and `{}`
  stay distinct, because the server distinguishes them (`meta` is `null` on
  automations, `{}` on prompts).

  **Baseline establishment.** `fetch` seeds state: when a local file and the
  remote record already agree semantically, both hashes and `version_id` are
  recorded; when they disagree, nothing is recorded and the item is reported as
  a conflict for a human. There is no migration from the old
  `~/.config/open-webui-cli/function-sync/` baselines — they hold a content
  hash without name, meta, or `version_id`, and a lossy conversion into a
  safety mechanism is worse than none. The old files stay untouched.

  **Absent state is a normal state, not an error.** `status` compares local
  against remote directly, so a fresh clone reports accurately; items without a
  recorded baseline read as `unbaselined`, and `push` refuses them. State only
  has to answer *who changed first*, never *what the truth is*.
- **D3 — Prompt files stay keyed by `command`; renames get assisted adoption.**
  Registry stores `{id, command, path}`; `status` flags "registered path
  missing + unregistered new file" with content similarity and offers `ow
  registry adopt`. GUID-keyed paths would make status quiet and the repo
  hostile; a rename is a normal edit the tool should recognize.
- **D4 — Automations promoted above prompts.** Record type, no version field,
  silent drift; the instance review cites RRULE/name disagreements and an
  `update_automation` silently re-pinning `model_id`. Dirty-diff gate plus
  always-explicit `model_id` in the file.
- **D5 — Skills file-set guard.** Push via `/import replace` deletes remote
  files absent locally, so `push` refuses when the local folder's file set
  differs from the last-fetched set unless `--allow-file-removal`. State
  stores a fetched file-set fingerprint, which covers **paths only** — a
  canonical sorted list, hashed — and not sizes or contents: a content edit is
  not a file-set change, and folding sizes in would make every edit look like
  a removal. It is read from `GET /api/v1/skills/id/{id}/files`, which returns
  `{version_id, files: [{path, size, encoding}]}`.
- **D6 — Read-only `status` for all types before any push adapter.**
  Normalization and equality-hash design is the load-bearing risk and is fully
  exercised read-only; push adapters then inherit trusted adapters.
- **D7 — Agent-facing surface split by verb.** `status`/`fetch` read-only,
  `push` writes, raw passthrough separate. The agent-facing entry point must
  not reach raw passthrough by import or by flag — the raw client stays
  importable in principle but not on the agent path.
- **D8 — Model commits carry provenance.** `commit_message` (accepted in the
  update payload) is written with the source git SHA, so the instance's own
  record names the commit it came from without trusting local state.
- **D9 — Portability boundary documented.** Model records reference instance
  KBs/files/tools by ID; the repo is authoritative for the record's own
  fields only.
- **D10 — Docstrings are the source of the artifact; nothing is double-homed.**
  Verified against the instance on 2026-11-08: function and tool docstrings
  carry `title`, `description`, `version`, `author`, `requirements`, and the
  server mirrors them into `meta.manifest` and `meta.description` verbatim. So
  there is no `meta.json` and no second home for description: the tracked file
  *is* the docstring. Authored meta the docstring cannot express (`i18n`,
  `toggle`, `type`, `has_user_valves`) is not stored either — push reads the
  server's current `meta`, overlays the derived fields, and sends it back, the
  way `sync.py` already preserves name and meta. Storing a toggle would
  reintroduce exactly the re-pin failure D1 forbids.
  - Consequence for `name`: it is a server-side label, not derived from the
    title (verified: 3 of 6 installed functions had a `name` that disagreed
    with the docstring title), so code types do not store it and push
    preserves it. Record types do store it, because it belongs to the JSON
    record they own.
  - Open: creating a *new* function needs `meta.type`, which now has no home
    in the file. Creation is a separate flow (`--create`), and this needs
    settling before that flow is built.
- **D11 — Prompt files: frontmatter carries identity, body round-trips
  byte-exactly.** `customizations/prompts/<command>.md` with frontmatter `id`,
  `command`, `name`, `tags`; the path is conventional-but-cosmetic, so a
  rename is a `git mv` at your discretion rather than an identity change —
  correlation comes from `id`, which is what makes D3's adoption flow
  reliable. Two mechanical constraints: (a) the body is everything after the
  closing delimiter minus exactly one newline, stored verbatim — OWUI prompt
  content is a plain string that may legitimately begin or end with newlines,
  which YAML folding and quoting would eat, producing a phantom content-hash
  diff on every fetch/push cycle; (b) no PyYAML — a strict subset parser (flat
  `key: value`, `[a, b]` lists) keeps the project dependency-free. `tomllib`
  is not an option: it is 3.11+, and this repo targets 3.9+.

## Two-way model

Per tracked item, `sync-state.json` records `file_hash` (hash of the local
file representation as of last sync), `equality_hash` (as above), and a
fetched-set fingerprint (D5).

| Local file | Remote record (equality hash) | Meaning |
| --- | --- | --- |
| unchanged | unchanged | In sync |
| changed | unchanged | Push candidate (with type-specific gate) |
| unchanged | changed | Pull candidate (`status` reports; `fetch` applies) |
| changed | changed | Conflict — reported, never auto-resolved |
| missing local | exists | Unregistered installed item → report |
| changed | ignored-field-only change | In sync (D1: excluded from comparison) |

Push safety mechanics shared by all adapters (from today's `sync.py`): read
the item, verify it still matches the snapshot, apply, read back and verify
content plus preserved fields, then advance state. Apply lock per instance;
nonzero exit on conflict/error; create-paths require explicit `--create`
(#4: see endpoint table). New items are never created implicitly.

## Push gates by type

- **Functions/tools**: local version must be higher (docstring
  `version: MAJOR.MINOR.PATCH`), existing name/meta/activation preserved.
- **Models**: dirty-file diff gate; `commit_message` = git SHA (D8); single
  item fetch/update — never the bulk `/models/sync` (it deletes).
- **Automations**: dirty-diff gate; explicit `model_id` always; re-read
  before write.
- **Prompts**: content push when file changed; rename → adoption flow (D3).
- **Skills**: whole-object replace only with `expected_version_id` recorded;
  file-set guard (D5); refusing missing files is the default.

## Gotchas & safeguards (updated against a real instance)

Verified on 2026-11-08 against the configured instance (6 functions, 8 tools,
37 models, 2 prompts, 2 skills, 4 automations):

- Tools are not one kind. The list mixes native Python tools with tool
  servers (`server:3`, `server:mcp:<id>`); servers are not file-managed and the
  adapter filters and reports them rather than failing.
- `meta` is `null` on automations, `{}` on prompts, and populated on
  functions/tools/models. Canonicalization must distinguish `null` from `{}`
  or hashes flap on every cycle.
- Skills' `content` already contains its own YAML frontmatter (the SKILL.md
  layout). Store it verbatim; do not wrap it in ours.
- Single-item GETs return `write_access`; `status` can report push-ability per
  item without a separate permission probe.
- Automations expose `next_run_at`/`next_runs`/`last_run`/`last_run_at` —
  runtime, live only, excluded from the projection.
- Model `export` inlines `background_image_data` (base64) and avatar file
  IDs; adapter strips payloads for git legibility (placeholder + hash).
- `access_grants` is never stored and never pushed (D1 bucket). Wanting them
  later is a D1 change, not an adapter change.
- `is_active`/`is_global`/`type` preserved on push; excluded from equality.
- Prompt command renames change `command`; adoption flow is user-resolved.
- Delete is never implied by `push`; removal is explicit.
- One checkout per instance (registry maps one path set); multi-instance
  registries deferred.

## Agent-facing surface (D7)

`ow status` and `ow fetch` are read-only against the instance. `ow push` is
the only writing verb. The raw client (`ow.client`) remains importable for
humans and scripts, but the agent-facing entry point cannot reach it — not
behind a flag an agent can pass, just absent from that path.

## Rollout (reordered per D6)

1. ✅ Phase 1 — Restructure, no behavior change (done: `ow` package, shim,
   `registry.json`; commit `8a102b0`, tag `v0.1.0`).
2. ✅ Phase 2 — `status`, read-only, all six types: file representation,
   canonicalization, equality-hash definition, committed `sync-state.json`
   format, seeded-baseline tests. No writes anywhere. Slices: (a) sanitized
   fixture capture from the instance, (b) adapter primitives — `from_file`,
   `to_file`, `project`, `eq_hash` — plus the table-driven
   "server-owned field mutated → hash unchanged" test, (c) state schema v1,
   (d) functions/tools, (e) models/prompts/automations, (f) skills file-set
   fingerprint, (g) `ow status` wiring and rename candidates. Done in v0.2.0
   plus the status slice.
3. Phase 3 — `fetch` (instance → repo) + registry/fetch state bookkeeping;
   `registry adopt` mechanics.
4. Phase 4 — Push pilots: functions & tools (version gate), then automations
   (dirty diff), models (provenance), prompts, skills (file-set guard).
5. Phase 5 — `ow push --commit` convenience, agent-facing surface split,
   multi-instance registries.

## Open decisions

- Skill attachments: repo-size policy for large binaries (cap, LFS, or
  out-of-repo) — safety is handled by D5 either way.
- Whether unregistered items get auto-registered by `fetch --register`, or
  offered via `registry adopt` only.
- Automation create-path endpoint needs verification on the 0.13.2 instance.

Resolved: state location (D2 rules; D1's "state file" meant *which* file, not
version control); `access_grants` (live only, never stored).
