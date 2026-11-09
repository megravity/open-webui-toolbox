# PLAN — open-webui-toolbox as the authoritative home for Open WebUI customizations

Status: proposal, not yet implemented. Target instance: Open WebUI 0.13.2 (re-verify adapter endpoints against it when building; some facts below come from current upstream `main` and can drift).

## Goal

`open-webui-toolbox` becomes the authoritative home for an instance's customizations.
All customization types are tracked in this repo as files; state outside the repo
records what was synced, so that:

- `fetch` pulls current customizations from the instance into files (instance → repo).
- `push` conservatively applies local files to the instance (repo → instance), first-class for Python code resources, standard for record-style resources.
- Git history is the change log; each commit is a reviewable step.

The raw authenticated API client and the management tooling are one integrated `ow`
binary: raw request passthrough stays available, customization commands are built
on top of the same client.

## Current state

| Component | Path | Role |
| --- | --- | --- |
| Raw API client | `cli/ow` | `setup`, `get/post/put/patch/delete`, chat/automation shortcuts, pagination, `jq` formatting, no-redirect policy |
| Function sync | `functions/sync.py` | Conservative, one-directional (local → remote) updates of registered functions; manifest-driven; baseline hashes outside the repo |
| Manifest | `functions/manifest.json` | Function ID → local path mapping (one entry: `publish_daily_check_in` → `filters/publish-daily-check-in/filter.py`) |
| Function sources | `filters/` | Current customization sources live here |
| Visual style | `visual-style/` | Reference assets; not API-managed, unchanged by this plan |

Integration issue today: `sync.py` already loads `cli/ow` via `runpy` to reuse
`load_config` and `NoRedirects` — two disconnected pieces pretending to be one.

## Verified API surface (per Open WebUI source, 0.12.5 era)

Endpoint paths relative to the instance base URL. Single-item paths are common to
all types where equal: `/api/v1/{type}/id/{id}` with `/update` and `/delete`.

| Type | Shape | Key endpoints |
| --- | --- | --- |
| Functions | Python `content`, `name`, `meta`, `type` (filter/pipe/action), `is_active`, `is_global` | `GET /api/v1/functions/list`, `GET /api/v1/functions/id/{id}`, `POST.../update` |
| Tools | Python `content` + server-generated `specs`, `name`, `meta` | `GET /api/v1/tools/` (fronted by `src/lib/apis/tools`), `GET /api/v1/tools/id/{id}`, `POST.../update` |
| Models | Plain JSON record: `base_model_id`, `name`, `meta`, `params`, `is_active`, `access_grants` (+ `commit_message` on update) | `GET /api/v1/models/all`, `GET /api/v1/models/export?ids=`, `POST /api/v1/models/import`, `POST /api/v1/models/sync` (bulk, **deletes**), `POST /api/v1/models/model/update` |
| Prompts | JSON record keyed by `id`, with `command`, `content`, tags, server-side `version_id` history | `GET /api/v1/prompts/`, `GET /api/v1/prompts/id/{id}`, `POST.../update` (content, creates a history entry), `POST.../update/meta`, `DELETE.../id/{id}/delete` |
| Skills | Markdown `content` + attached **files** (SKILL.md layout), `description`, `meta`, `is_active`, `access_grants`, `version_id` history, zip import/export | `GET /api/v1/skills/`, `GET /api/v1/skills/id/{id}`, `POST.../update`, `GET /api/v1/skills/export`, `DELETE.../id/{id}/delete`, `GET .../id/{id}/files`, history endpoints |

Common rules:

- All requests need the admin-API-key conventions already used (functions/manage endpoints expect administrator access; the skill import/replace paths validate `access_grants` and can filter grants the caller may not assign).
- No server-side compare-and-swap on functions/tools/models; skills replacement (`/import` with action `replace`) requires `expected_version_id`; skills and prompts expose `version_id` we can harden with.
- The web UI tolerates the instance owning items the key's user cannot write; fetch must handle 403 on individual items as a report, not a failure.

## Target layout

```
open-webui-toolbox/
  ow/                      # one package, one entry point
    client.py              # raw API client (moved from cli/ow verbatim in behavior)
    config.py              # load_config, paths, per-instance state locations
    state.py               # sync-state format + 3-way compare
    manage/
      functions.py  tools.py  models.py  prompts.py  skills.py   # adapters
  cli/ow                   # thin shim → ow, kept for one transition period
  customizations/
    functions/             # <id>.py  (filters/ files move here under their IDs)
    tools/                 # <id>.py
    models/                # <id>.json  (canonical JSON, stable key order)
    prompts/               # <command>.md  (frontmatter: name, tags; body = content)
    skills/                # <skill-id>/SKILL.md + attached files (native .skill layout)
  registry.json            # replaces functions/manifest.json: {type, id → path}
```

Commands after integration:

```
ow setup                                    # unchanged
ow get /api/...  [-d ...] [--raw]           # unchanged raw passthrough, incl. -c/-a shortcuts
ow fetch [type...]                          # instance → files, update registry, refresh state
ow status [type...]                         # per-item 3-way summary
ow push [type...] [--all]                   # gated apply of local files (today's sync behavior)
```

## Two-way model

Per tracked item, state records the content hashes of **local file and remote
record as of the last successful sync**: `{local_hash, remote_hash}`. Transitions:

| Local file | Remote record | Meaning |
| --- | --- | --- |
| == last local | == last remote | In sync (clean) |
| changed | unchanged | Push candidate |
| unchanged | changed | Pull candidate (`status` reports; `fetch` applies) |
| changed | changed | Conflict — reported, never auto-resolved |
| missing local | exists | Unregistered installed item → report (optionally `--register`) |
| exists outside registry | — | Same report; registry stays authoritative |

Push gates differ by type, but the safety mechanics are shared (from today's
`sync.py`): read the item, verify it still matches the snapshot, apply, read back
and verify content + preserved fields, then advance state. Nonzero exit on any
conflict/error; apply lock per instance; state never silently replaced.

- **Functions/tools**: local version must be higher than installed (docstring
  `version: MAJOR.MINOR.PATCH`), existing name/meta/activation preserved.
- **Models**: no version field — gate is a dirty file diff (like the push
  contract for JSON resources); verify-after-write where the API allows.
- **Prompts**: updating content creates a server-side history entry, so history
  is a bonus review layer; push only when file changed.
- **Skills**: server-side `version_id` enables real optimistic concurrency —
  record `version_id`, refuse push when it changed (unless explicitly retried
  with `--force-replace` to re-read and rewrite `expected_version_id`).

State lives outside the repo (same XDG convention as today:
`~/.config/open-webui-cli/sync/<url-hash>.json`), one file per instance URL.
It stores hashes and IDs only, never source.

## Adapter contract

Each adapter in `ow/manage/<type>.py` implements, roughly:

- `list_remote()` — enumerate installed items (all pages, only what the key can read).
- `read_remote(id)` — fetch one record (403 or missing handled as per-item report).
- `to_file(record)` — deterministic file representation (see layout; JSON types canonicalized for stable hashes/diffs; model record fields that are instance-local — `user.id`, `updated_at`, big data URIs — normalized/hashed, see Gotchas).
- `from_file(path)` — parse the same representation.
- `push(record, remote, gate)` — type-specific gate (version bump vs. dirty diff) + shared check,apply,verify,advance mechanics.

One shared `state.py` + one shared `fetch`/`status`/`push` driver; adapters stay
small. Models are the only type with a foreign bulk endpoint (`/models/sync`) —
deliberately **not** used: it deletes anything not in the payload and is too
destructive for a hand-reviewed, file-per-item workflow.

## Gotchas & safeguards

- **Model background images**: `/models/export` inlines `background_image_data` as base64 data URIs, and avatar references are file IDs only. Adapter strips binary payloads into side files (or placeholder + hash) so git stays reviewable; document that importing a stripped model to a *different* instance loses/rejects those.
- **`access_grants`** can be filtered/rewritten by the server based on caller permissions. First version: record-and-preserve, do not push grant changes; revisit later.
- **`is_active` / `is_global` / `type`** on functions: preserved on push (as today), snapshotted/reflected in fetch.
- **Prompt command renames** create ID changes; treat rename as delete+create pairs, prompted.
- **Delete is never implied**: `ow push` adds/updates; removing an item from Open WebUI stays manual (or a future explicit `ow delete <type> <id>`).
- **Two instances / one checkout** is out of scope for v1; state is per-URL but the registry maps one path set — plan: one clone per instance, or later, instance-scoped registries.

## Rollout

1. **Phase 1 — Restructure, no behavior change.** `ow` package + `cli/ow` shim; move raw client unchanged; `registry.json` generation from `functions/manifest.json`; relocate `functions/manifest.json` users; keep test suite passing.
2. **Phase 2 — Fetch/status core + functions & tools (pilot).** Two types, one adapter family; migrate `function-sync` baselines into the shared state format; extend simulated-API unittest pattern to fetch/status.
3. **Phase 3 — Models.** Canonical JSON, data-URI stripping, single-item fetch/update.
4. **Phase 4 — Prompts.** Markdown + frontmatter; server-side history note.
5. **Phase 5 — Skills.** Folder-per-skill layout; optimistic concurrency via `version_id`/`expected_version_id`; file upload round-trip.
6. **Later — Automations** (the client already has shortcuts) and multi-instance registries.

Each phase is independently shippable; the raw client never stops working.

## Open decisions

- Push authorization UX: default preview (status-style listing) with `--apply`/`push --all`? (Proposed: yes — same as today's `sync` defaults.)
- Skill file upload strategy for fetch: which files to commit when a skill has many attachments (cap size, store large binaries out of repo or as LFS).
- Whether `fetch` of an already-registered-but-deleted-remotely item should delete the local file or flag it (proposed: flag).
- Feedback wanted on CLI ergonomics before Phase 2 implementation starts.
