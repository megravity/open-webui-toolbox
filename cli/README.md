# Open WebUI CLI

A tiny wrapper for authenticated Open WebUI API calls. Requires Python 3 and `jq` for formatted JSON output. The implementation lives in the [`ow/`](../ow/) package; `cli/ow` is a thin launcher script, and setup and usage are unchanged.

## Setup

```sh
cd /Users/megravity/Projects/open-webui-toolbox/cli
./ow setup
```

Enter the instance's base URL and your Open WebUI API key when prompted. Find or create the key in Open WebUI under **Settings → Account**. API keys must be enabled for your account. The key has the permissions of that account; use an appropriately restricted account. See the [Open WebUI API key documentation](https://docs.openwebui.com/features/authentication-access/api-keys/).

The URL and key are stored together in `~/.config/open-webui-cli/config.json`, outside this repository and readable only by your user (mode 600). Keep it private and out of backups you do not trust. Run setup again to replace it. If `XDG_CONFIG_HOME` is set, its `open-webui-cli/config.json` is used instead. To use another file, set `OPENWEBUI_CONFIG` before setup and each request.

## Use

```sh
./ow get /api/models
./ow get /api/models --raw
./ow get '/api/v1/chats/?page=1'
./ow get --chat
./ow get --chat CHAT_ID
./ow delete -c CHAT_ID
./ow get --automation
./ow get -a AUTOMATION_ID
./ow delete --automation AUTOMATION_ID
./ow status
./ow status prompts
./ow status --check
./ow post /api/chat/completions -d '{"model":"MODEL_ID","messages":[{"role":"user","content":"Hello!"}]}'
./ow post /some/api/path -d @payload.json
cat payload.json | ./ow post /some/api/path -d @-
./ow delete /some/api/path
```

Supported methods are `get`, `post`, `put`, `patch`, and `delete`. `-d` sends a JSON request body literally, from a file (`@filename`), or from standard input (`@-`). JSON responses are formatted with `jq` by default; use `--raw` to receive the exact response bytes (for example, for downloads or further processing). Non-JSON responses are unchanged. If `jq` is unavailable or fails, the original response is returned with a warning. HTTP errors go to standard error unchanged and produce a nonzero exit status. Redirects are not followed so credentials cannot be forwarded to another destination; use the correct base URL.

`status` reports how the customizations listed in the repository's `registry.json` compare with the configured instance. It is read-only. Each item gets one verdict: `in-sync`, `push-candidate`, `pull-candidate`, `conflict`, `unbaselined` (no recorded baseline yet; run `fetch` when it exists), `missing-local`, `missing-remote`, `path-moved` (a tracked prompt file moved but kept its ID), or `state-inconsistent` (the recorded baseline matches neither side). Items installed on the instance but absent from the registry are listed as `remote-unregistered`. Pass one or more types (`functions`, `tools`, `models`, `prompts`, `skills`, `automations`) to narrow the report. The command exits 0 even when items conflict; add `--check` to exit nonzero on conflicts, for CI. Errors and inconsistent state always exit nonzero.

`-c` / `--chat` and `-a` / `--automation` are shortcuts that take the place of the API path. With `get`, omit the ID to list all of that account's chats or automations. Chat lists include pinned, folder, and archived chats; automation and archived chat lists fetch every page. These list shortcuts combine responses into one JSON array, so `--raw` returns the unformatted combined array. Since pages are fetched separately, changes while listing can affect the result.

With an ID, the chat shortcut works with each HTTP method. The automation shortcut supports `get`, `post` (update), and `delete`. IDs must contain only letters, numbers, hyphens, or underscores. An ID is required for every shortcut except `get`, and deleting an item removes it from Open WebUI. Use `./ow get --help` or `./ow delete --help` for command options.

For a shorter command from any directory, add this directory to your shell's `PATH`, or call the script by its full path. See the [API reference](https://docs.openwebui.com/reference/api-endpoints/) and your instance's `/docs` for available endpoints.
