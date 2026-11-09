# Open WebUI toolbox

Standalone utilities for working with Open WebUI.

- [CLI](cli/README.md): make authenticated API calls, list chats and automations, and target individual items. The implementation lives in [`ow/`](ow/); [`cli/ow`](cli/ow) is a thin launcher.
- [Function sync](functions/README.md): preview and apply conflict-checked function updates from local files listed in [registry.json](registry.json).
- [Filters](filters/README.md): reusable Open WebUI filter functions and their usage notes.
- [Visual style](visual-style/README.md): reference assets and design guidance for the Open WebUI instance.

Each utility lives in its own directory with its own usage instructions. Instance configuration and credentials stay outside this repository.

[PLAN.md](PLAN.md) tracks the roadmap for making this repository the authoritative home for Open WebUI customizations.
