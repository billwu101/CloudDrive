from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentUserId, DbSession
from app.schemas.common import DriveItemResponse, Page
from app.search.repository import SQLSearchRepository
from app.search.service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


def _search_service(session: DbSession) -> SearchService:
    return SearchService(repo=SQLSearchRepository(session))


SearchServiceDep = Annotated[SearchService, Depends(_search_service)]


@router.get("", response_model=Page[DriveItemResponse], summary="Search drive items")
async def search(
    q: str,
    current_user_id: CurrentUserId,
    service: SearchServiceDep,
    item_type: str | None = None,
    mime_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[DriveItemResponse]:
    return await service.search(
        current_user_id,
        q,
        item_type=item_type,
        mime_type=mime_type,
        page=page,
        page_size=page_size,
    )
