"""Configuration storage for the Open WebUI CLI."""

import getpass
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit


CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config").expanduser()
CONFIG = Path(os.environ.get("OPENWEBUI_CONFIG") or CONFIG_DIR / "open-webui-cli" / "config.json").expanduser()


def base_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.netloc
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or any(c.isspace() for c in value)):
        raise ValueError("URL must be an http(s) URL without credentials, query, or fragment")
    return value.rstrip("/")


def setup():
    url = base_url(input("Open WebUI URL (e.g. http://localhost:3000): ").strip())
    key = getpass.getpass("Open WebUI API key: ").strip()
    if not key or "\n" in key or "\r" in key:
        raise ValueError("API key cannot be empty or contain a newline")
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".ow-", dir=CONFIG.parent)
    try:
        with os.fdopen(fd, "w") as file:
            json.dump({"url": url, "api_key": key}, file)
            file.write("\n")
        os.replace(temp_name, CONFIG)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    print(f"Saved configuration to {CONFIG}")


def load_config():
    try:
        with CONFIG.open() as file:
            config = json.load(file)
        url = base_url(config["url"])
        key = config["api_key"]
        if not isinstance(key, str) or not key or "\n" in key or "\r" in key:
            raise ValueError("invalid API key")
        return url, key
    except FileNotFoundError:
        raise ValueError("No configuration found. Run ./ow setup first.") from None
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid configuration: {exc}. Run ./ow setup again.") from None
