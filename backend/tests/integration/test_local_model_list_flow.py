"""Server-provided model list — proposal §12 "本機模型清單" / design §11.10.5.

The point of the feature is that a model offered by the deployment reaches
*every* user with no per-account setup, so the tests that matter are the ones a
per-user mechanism would fail: a brand-new account seeing the whole list, and
the same list appearing for two unrelated users.

`ASSISTANT_MODELS` is read through `get_settings()`, which is `lru_cache`d and
already warm by the time a test runs, so these rebuild `Settings` directly for
the parsing rules and drive the endpoint for everything else.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import Settings, get_settings
from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio

MODELS = "/api/v1/assistant/models"
CONNECTIONS = "/api/v1/users/me/model-connections"


async def test_the_default_model_always_leads_the_list() -> None:
    """An unspecified target resolves to `assistant_model`, so the picker's
    first entry has to be that same model or the two disagree."""
    s = Settings(assistant_model="qwen3.6:35b", assistant_models="gemma4:31b,qwen3.8:27b")
    assert s.local_model_ids == ["qwen3.6:35b", "gemma4:31b", "qwen3.8:27b"]


async def test_an_unset_list_behaves_exactly_as_before() -> None:
    """The feature has to be invisible to a deployment that never sets it."""
    assert Settings(assistant_model="gemma4:26b", assistant_models="").local_model_ids == [
        "gemma4:26b"
    ]


@pytest.mark.parametrize(
    "raw",
    [
        " gemma4:31b , qwen3.8:27b ",  # padding around entries
        "gemma4:31b,,qwen3.8:27b,",  # empty entries
        "gemma4:31b,qwen3.8:27b,gemma4:31b",  # a repeat
        "qwen3.6:35b,gemma4:31b,qwen3.8:27b",  # the default listed again
    ],
)
async def test_the_list_is_normalised(raw: str) -> None:
    """Hand-edited env values are messy; none of these should produce a
    duplicate entry or a blank one in the user's picker."""
    s = Settings(assistant_model="qwen3.6:35b", assistant_models=raw)
    assert s.local_model_ids == ["qwen3.6:35b", "gemma4:31b", "qwen3.8:27b"]


async def test_a_brand_new_account_sees_every_server_model(client: AsyncClient) -> None:
    """The whole reason this exists: no per-account setup, no rows to create.

    A user who has never opened Settings, and owns no connection, still gets the
    full list on their first request.
    """
    fresh = auth_headers(
        await register_and_login(client, email="lm-fresh@test.com", username="lmf")
    )

    resp = await client.get(MODELS, headers=fresh)
    assert resp.status_code == 200, resp.text
    options = resp.json()

    expected = get_settings().local_model_ids
    assert [o["id"] for o in options] == ["local"] + [f"local:{m}" for m in expected[1:]]
    assert [o["label"] for o in options] == [f"Local ({m})" for m in expected]
    assert all(o["available"] for o in options)

    # And no connection was created behind the scenes to make that happen.
    conns = await client.get(CONNECTIONS, headers=fresh)
    assert conns.json() == []


async def test_two_unrelated_users_get_the_same_server_list(client: AsyncClient) -> None:
    """A per-user mechanism would give these two different answers."""
    a = auth_headers(await register_and_login(client, email="lm-a@test.com", username="lma"))
    b = auth_headers(await register_and_login(client, email="lm-b@test.com", username="lmb"))

    ids_a = [o["id"] for o in (await client.get(MODELS, headers=a)).json()]
    ids_b = [o["id"] for o in (await client.get(MODELS, headers=b)).json()]
    assert ids_a == ids_b


async def test_the_bare_local_id_is_kept_for_older_clients(client: AsyncClient) -> None:
    """`local` predates the list and is what a client sends when it has no
    opinion, so it must stay addressable and keep its original label."""
    h = auth_headers(await register_and_login(client, email="lm-compat@test.com", username="lmc"))

    first = (await client.get(MODELS, headers=h)).json()[0]
    assert first["id"] == "local"
    assert first["label"] == f"Local ({get_settings().assistant_model})"


async def test_an_unknown_local_model_is_refused_by_name(client: AsyncClient) -> None:
    """A target the deployment does not serve must say so, rather than quietly
    falling back to the default and answering as a different model than the one
    the user picked."""
    h = auth_headers(await register_and_login(client, email="lm-bogus@test.com", username="lmbg"))

    resp = await client.post(
        "/api/v1/assistant/chat",
        json={"message": "hello", "model": "local:not-a-real-model"},
        headers=h,
    )
    assert resp.status_code >= 400, resp.text
    body = resp.json()
    assert body["error"]["code"] == "ASSISTANT_UNAVAILABLE"


async def test_server_models_and_personal_connections_coexist(client: AsyncClient) -> None:
    """The two mechanisms answer different needs (deployment-owned vs
    user-owned credentials) and must not displace each other."""
    h = auth_headers(await register_and_login(client, email="lm-both@test.com", username="lmboth"))

    server_ids = [o["id"] for o in (await client.get(MODELS, headers=h)).json()]

    created = await client.post(
        CONNECTIONS,
        json={
            "label": "Personal",
            "kind": "openai_compatible",
            "base_url": "http://127.0.0.1:9/v1",
            "model": "gpt-test",
            "secret": "sk-not-real",
        },
        headers=h,
    )
    assert created.status_code == 200, created.text

    after = [o["id"] for o in (await client.get(MODELS, headers=h)).json()]
    assert after == [*server_ids, created.json()["id"]]
