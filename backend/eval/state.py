from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


class StateFetchError(Exception):
    """Raised when the post-run drive state cannot be read from the backend."""


def _fetch_page(
    base_url: str, token: str, *, parent_id: str | None, timeout: float
) -> list[dict[str, Any]]:
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
    return [item for item in items if isinstance(item, dict)]


def fetch_items_http(
    base_url: str,
    token: str,
    *,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """Snapshot root items *plus one level of children for every root folder*
    (for E1 state assertions, including item_starred/item_parent — 2026-07-27
    E9). One level is enough for these tests: everything is seeded at root or
    moved once into a root-level destination folder. Returns raw item dicts
    (id/name/item_type/is_starred/parent_id/...), not just names."""

    root = _fetch_page(base_url, token, parent_id=None, timeout=timeout)
    items = list(root)
    for item in root:
        if item.get("item_type") == "FOLDER" and item.get("id"):
            items.extend(_fetch_page(base_url, token, parent_id=item["id"], timeout=timeout))
    return items


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

    items = _fetch_page(base_url, token, parent_id=parent_id, timeout=timeout)
    return [item.get("name", "") for item in items]
