"""Authenticated JSON requests against an Open WebUI instance."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from ow.client import NoRedirects


class HttpError(RuntimeError):
    """A response with an error status, keeping the code for callers."""

    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


class Api:
    """Minimal JSON client; the raw CLI and the adapters share it."""

    def __init__(self, base_url, key, handler=None):
        self.base_url = base_url
        self.key = key
        self.opener = build_opener(handler or NoRedirects())

    def request(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.key}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=60) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            raise HttpError(exc.code) from None
        except (URLError, OSError, ValueError) as exc:
            raise RuntimeError(f"request failed ({type(exc).__name__})") from None
