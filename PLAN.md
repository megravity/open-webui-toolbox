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
single-item reads is a report, not a failure), no server-side CAS for
functions/tools/models; skills replacement and prompt/skill sets of
`version_id` support optimistic concurrency where offered.

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

- **D1 — Two derived values per item.** *File representation* (everything,
  for humans and git) vs *equality hash* over exactly the fields push applies
  (functions/tools: `content`+`name`+`meta`, not `is_active`/`is_global`/`specs`;
  models: record fields minus instance-owned; prompts: content+command+name+
  tags, not `version_id`; skills: content+description+meta+files, not
  `version_id`/auth fields; automations: config incl. explicit `model_id`, not
  `updated_at`). Server-owned or push-ignored fields are *excluded from
  comparison*, not normalized. Enforced as a declarative controlled-field list
  per adapter, exercisable via read-only `status` with a seeded baseline. An
  earlier single-hash state format would make `status` permanently dirty after
  any UI edit to ignored fields.
- **D2 — Sync state is committed in the repo.** `{local, remote}` hashes are
  history, not derivable; outside the repo a fresh clone reads as all-changed.
  `sync-state.json` at repo root stores hashes and IDs only. Pairing rule: a
  change commit always carries its state update together (discipline in v1;
  tool-side `--commit` later). Alternatives considered: derive-from-git
  (breaks under amend/rebase), expendable external state (re-fetch + manual
  reconcile).
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
  stores a fetched file-set fingerprint.
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

## Gotchas & safeguards (updated)

- Model `export` inlines `background_image_data` (base64) and avatar file
  IDs; adapter strips payloads for git legibility (placeholder + hash).
- `access_grants` server-validated; record, don't push (first version).
- `is_active`/`is_global`/`type` preserved on push; excluded from equality.
- Prompt command renames change IDs; adoption flow is user-resolved.
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
2. Phase 2 — `status`, read-only, all six types: file representation,
   canonicalization, equality-hash definition, committed `sync-state.json`
   format, seeded-baseline tests. No writes anywhere.
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
