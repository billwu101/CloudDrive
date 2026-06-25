from __future__ import annotations

import json
import urllib.parse
import urllib.request


class StateFetchError(Exception):
    """Raised when the post-run drive state cannot be read from the backend."""


def fetch_item_names_http(
    base_url: str,
    token: str,
    *,
    parent_id: str | None = None,
    timeout: float = 30.0,
) -> list[str]:
    """Snapshot the user's drive item names from a live backend (for E1 state
    assertions). Reads one page of `GET /drive/items`; safety checks only need
    presence/absence of a named item in the listing."""

    query = {"page_size": "200"}
    if parent_id is not None:
        query["parent_id"] = parent_id
    url = f"{base_url.rstrip('/')}/drive/items?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url, method="GET", headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
    except Exception as exc:  # surfaced as a state error
        raise StateFetchError(f"failed to read drive state: {exc}") from exc
    items = body.get("items", []) if isinstance(body, dict) else []
    return [item.get("name", "") for item in items if isinstance(item, dict)]
