# Open WebUI function sync

Preview and apply updates to registered functions on the configured Open WebUI instance. The script was designed for Open WebUI 0.13.2 and uses the [CLI's configuration](../cli/README.md); its API key must belong to an administrator. It uses Python 3.9 or newer and the standard library.

```sh
./functions/sync.py          # Preview only
./functions/sync.py --apply  # Record matching baselines and apply safe updates
```

The [registry](../registry.json) maps each installed function ID to a local Python source file. Add an entry to its `functions` map when another function should be managed. The source must have a module docstring containing exactly one `version: MAJOR.MINOR.PATCH` line with numeric components; pre-release and other version formats are not supported.

## How updates are checked

1. The script reads the installed functions and compares the source of each registered, installed function with its local file. It reports unregistered installed functions and does not create missing functions.
2. When the two sources are identical and no baseline exists, `--apply` records a hash of the installed source. Preview reports that a baseline can be recorded but writes nothing. An existing baseline is never silently replaced if the installed source differs.
3. For an update, the local version must be higher and the installed source must match the previously recorded baseline. Otherwise, the script skips it and reports a conflict. It also skips source changes with the same or a lower version. Increase the version when changing a function.
4. Immediately before an update, the script reads the function again and checks that its source, name, metadata, type, activation flags, and update time have not changed. It sends the existing name and metadata with the new source, then reads the function back and checks the source and activation flags before advancing the baseline.

There is no server-side compare-and-swap in this workflow: another editor can still change a function between the final check and the update. Avoid editing the same function while an apply is running. An apply lock prevents simultaneous runs of this script for the same configured instance; it cannot lock the Open WebUI editor or other API clients.

Baselines are stored outside the repository under `${XDG_CONFIG_HOME:-~/.config}/open-webui-cli/function-sync/`, with a separate file per configured instance URL. They contain function IDs and source hashes, not source code or credentials. Moving or deleting that state, or changing the configured URL, requires establishing a new baseline from identical local and installed source. If the installed source has diverged, review and reconcile it before establishing a baseline; the script never overwrites it automatically.

The script preserves the existing function's active and global settings and does not read or update valves. Open WebUI validates existing valves when loading an update. A failed response or verification after an update request can have an uncertain outcome: inspect the installed function before trying again. Pending in-memory tasks may also be affected by process restarts; sync does not restart Open WebUI.

The script returns a nonzero status for conflicts, same-or-lower-version source differences, and request failures. A missing function is reported and skipped. To run the local simulated API tests:

```sh
python3 -m unittest discover -s functions -p 'test_*.py'
```
