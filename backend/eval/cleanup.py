"""Delete the throwaway accounts a run created (2026-07-29).

``run_isolated_e9`` registers one user per (case, run) so cases cannot pollute
each other. Nothing ever removed them: a single day of batches left **955**
accounts and ~13k drive items behind, and cleaning them up by hand meant
hand-writing a cascade delete across 18 foreign keys — exactly the kind of
chore that gets skipped until the dev database is unusable.

Scoped to the emails this run actually created, never a blanket ``e9_%``: two
batches may run at once (they do — one per model endpoint), and wiping the
other one's users mid-run would corrupt its results rather than tidy up.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.models import Base
from app.models.user import User


def _user_foreign_keys() -> list[tuple[str, str]]:
    """Every ``(table, column)`` that points at ``users.id``, in delete order.

    Derived from the ORM metadata rather than hard-coded: a new table with a
    user FK would otherwise make cleanup fail with an integrity error long
    after whoever added it moved on.
    """

    pairs: list[tuple[str, str]] = []
    for table in reversed(Base.metadata.sorted_tables):
        if table.name == User.__tablename__:
            continue
        for column in table.columns:
            for foreign_key in column.foreign_keys:
                if foreign_key.column.table.name == User.__tablename__:
                    pairs.append((table.name, column.name))
    return pairs


async def _delete(emails: list[str]) -> int:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            ids = (
                (await conn.execute(select(User.id).where(User.email.in_(emails)))).scalars().all()
            )
            if not ids:
                return 0
            for table_name, column in _user_foreign_keys():
                await conn.execute(
                    text(f'DELETE FROM "{table_name}" WHERE {column} = ANY(:ids)'), {"ids": ids}
                )
            await conn.execute(delete(User).where(User.id.in_(ids)))
            return len(ids)
    finally:
        await engine.dispose()


def delete_test_users(emails: list[str]) -> int:
    """Remove those users and everything hanging off them. Returns the count.

    Best-effort: a cleanup failure must never fail a finished batch, so the
    caller reports the error and keeps the results.
    """

    if not emails:
        return 0
    return asyncio.run(_delete(emails))
