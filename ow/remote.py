"""Reading customizations from an instance.

List endpoints are cheap but omit what comparison needs: functions have no
`content` field and tools carry `content: null`. So listing answers "which IDs
exist" and a per-item read answers "what is it".
"""

from urllib.parse import quote

LIST = {
    "functions": "/api/v1/functions/list",
    "tools": "/api/v1/tools/",
    "models": "/api/v1/models/all",
    "prompts": "/api/v1/prompts/",
    "skills": "/api/v1/skills/",
    "automations": "/api/v1/automations/list",
}

ONE = {
    "functions": "/api/v1/functions/id/{}",
    "tools": "/api/v1/tools/id/{}",
    "models": "/api/v1/models/model?id={}",
    "prompts": "/api/v1/prompts/id/{}",
    "skills": "/api/v1/skills/id/{}",
    "automations": "/api/v1/automations/{}",
}

# Types whose list endpoint returns complete records, so no per-item read.
COMPLETE = ("models",)

# Tool IDs of this shape are tool servers, not tracked Python files.
SERVER_PREFIX = "server:"


def is_manageable(type_name, identifier):
    return not (type_name == "tools" and identifier.startswith(SERVER_PREFIX))


def _items(type_name, payload):
    if type_name == "automations":
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise RuntimeError("unexpected automation list response")
        return payload["items"], payload.get("total")
    if not isinstance(payload, list):
        raise RuntimeError(f"unexpected {type_name} list response")
    return payload, None


def listing(api, type_name):
    """Return every installed ID of a type, skipping unmanageable entries."""
    payload = api.request("GET", LIST[type_name])
    items, total = _items(type_name, payload)
    if type_name == "automations":
        page = 1
        seen = len(items)
        while isinstance(total, int) and seen < total:
            page += 1
            more, more_total = _items(type_name, api.request("GET", LIST[type_name] + f"?page={page}"))
            if not more:
                break
            items = items + more
            seen = len(items)
            total = more_total if isinstance(more_total, int) else total
    identifiers = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise RuntimeError(f"unexpected {type_name} list entry")
        if is_manageable(type_name, item["id"]):
            identifiers.append(item["id"])
    return identifiers


def read(api, type_name, identifier, listed=None):
    """Return one full record, using a listed record when it is complete."""
    if type_name in COMPLETE and listed is not None:
        return listed
    return api.request("GET", ONE[type_name].format(quote(identifier, safe="")))


def records(api, type_name):
    """Return {id: record} for every manageable installed item of a type."""
    if type_name in COMPLETE:
        payload = api.request("GET", LIST[type_name])
        if not isinstance(payload, list):
            raise RuntimeError(f"unexpected {type_name} list response")
        return {item["id"]: item for item in payload
                if isinstance(item, dict) and isinstance(item.get("id"), str)
                and is_manageable(type_name, item["id"])}
    return {identifier: read(api, type_name, identifier)
            for identifier in listing(api, type_name)}


class Remote:
    """A reader bound to one instance, so callers can substitute a fake."""

    def __init__(self, api):
        self.api = api

    def listing(self, type_name):
        return listing(self.api, type_name)

    def read(self, type_name, identifier):
        return read(self.api, type_name, identifier)
