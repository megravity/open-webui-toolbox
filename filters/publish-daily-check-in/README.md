# Publish daily check-in

Version 0.2.1 by Marvin. The [filter.py](filter.py) posts an assistant answer to a configured webhook when the latest user message contains a marker. After a successful HTTP response, it can schedule the chat for deletion. It returns the original conversation body unchanged.

Version 0.2.1 retains references to scheduled deletion tasks until they finish, preventing them from being garbage-collected while pending. The valves and their defaults are unchanged from 0.2.0.

The filter checks the marker, not whether the request is actually an automation. A matching message in any chat where this filter runs can publish that chat's answer and, if configured, delete the chat. Restrict where the filter is active and use a dedicated automation model; this reduces exposure but does not prevent a user of that model from triggering it.

## Setup

1. In **Admin Panel → Functions**, create a function and paste the contents of [filter.py](filter.py). Save it and configure its valves using the gear icon. See the [Open WebUI functions documentation](https://docs.openwebui.com/features/extensibility/plugin/functions/).
2. Set `webhook_url` to a reachable endpoint that accepts a JSON `content` field. Treat the URL as a secret. Set `delete_chat` to `false` for an initial test.
3. Activate the filter and attach it to the automation's model under **Workspace → Models → Filters**. Avoid making it global unless every model should be subject to its trigger.
4. Include the configured marker in the automation's latest user message. Run a disposable test and check the destination and Open WebUI logs for `[checkin-publish]`. Confirm that the endpoint, automation, and installed Open WebUI version run the outlet as expected; this repository does not establish a live integration test.
5. If deletion is desired, configure `api_base_url` and a dedicated `delete_api_key` with only the access needed to delete the automation's chats. Set `delete_chat` to `true` and test using a disposable chat. A successful webhook response schedules deletion; it does not guarantee delivery to a reader or successful deletion.

Do not put the webhook URL or API key in this repository. Configure them in the function's admin valves. Limit access to those settings and to the model or function as appropriate for the instance.

## Valves

| Valve | Default | Purpose |
| --- | --- | --- |
| `webhook_url` | empty | Webhook receiving `POST` JSON in the form `{"content": "<answer>"}`. An empty value skips publishing. |
| `marker` | `[[daily-checkin]]` | Literal, case-sensitive substring required in the latest user message. An empty or whitespace-only marker disables publishing. |
| `api_base_url` | `http://open-webui:8080` | Base URL reachable from the Open WebUI process for the deletion API. Adjust for the deployment. |
| `delete_api_key` | empty | Bearer token used for chat deletion. An empty value skips deletion. |
| `delete_chat` | `true` | Whether to schedule deletion after a successful webhook response. |
| `delete_delay_seconds` | `90` | Delay before deletion; negative values are treated as zero. |

## Behavior and limitations

- The filter looks for the last assistant message after the latest user message. Missing, empty, or non-string content is not published; older answers before that user message are ignored.
- A non-success webhook response or request error is logged and does not schedule deletion. The filter has no retry or deduplication: repeated outlet calls can publish duplicates, and a transient failure loses that attempt.
- Deletion requires a successful webhook request, enabled deletion, a base URL, a key, and `chat_id` in `__metadata__`. The background deletion task is in memory; a restart or shutdown during the delay can lose it. Delete failures are logged and not retried.
- The 90-second delay is a fixed wait, not confirmation that the automation or chat persistence has finished. The code does not verify that the chat is a disposable automation run.
- The webhook URL and API key are not printed by the filter. Logs include response status, answer length, and, for deletion results, the chat ID. Check destination-specific message limits and webhook requirements before relying on delivery.
