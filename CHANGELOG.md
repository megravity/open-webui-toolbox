# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the versioning scheme is [SemVer](https://semver.org/spec/v2.0.0.html). See
[AGENTS.md](AGENTS.md) for the versioning rules.

## [Unreleased]

### Added

- Canonical hashing and per-type adapters in `ow/manage/` for functions,
  tools, models, prompts, skills, and automations: each knows its tracked file
  format, which fields a push controls, and how to compare local against
  remote. Server-owned and live-only fields (activation flags, `specs`,
  `version_id`, timestamps, access grants) are excluded from comparison, so a
  UI toggle is not misread as upstream drift.
- `ow/state.py`, the committed `sync-state.json` format: hashes, `version_id`
  tokens, and the instance URL, with validation, atomic writes, and no-op
  writes that leave the tree byte-identical. No command consumes it yet.

## [0.1.0] — 2026-11-08

### Added

- CLI (`cli/ow`): authenticated raw Open WebUI API client with
  `get`/`post`/`put`/`patch`/`delete`, chat and automation shortcuts,
  paginated listings, and a no-redirect credential policy. Instance URL and
  API key live outside the repo in `~/.config/open-webui-cli/` (`b868bbe`).
- Filter `publish-daily-check-in`: publishes an automation's final answer to a
  webhook and can schedule the run's chat for deletion; includes usage notes
  and valve documentation (`5240440`).
- Function sync (`functions/sync.py`): preview and apply conflict-checked
  function updates from local files, with recorded baselines, an apply lock,
  version-gated pushes, and post-update verification (`f307ab3`).
- Visual style reference assets and guidance (`5240440`).
- Integration plan (PLAN.md) for making this repository the authoritative home
  for Open WebUI customizations (`accc063`).

### Changed

- Restructured the CLI into the `ow` package (`ow/config.py`, `ow/client.py`);
  `cli/ow` is a thin launcher shim with unchanged behavior, messages, and exit
  codes (`8a102b0`).
- Function sync now reads the root `registry.json` — a JSON map of function ID
  to local source file — with duplicate-key rejection, replacing
  `functions/manifest.json`; registry parsing covered by tests (`8a102b0`).
