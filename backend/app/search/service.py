from __future__ import annotations

from uuid import UUID

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.schemas.common import DriveItemResponse, Page
from app.search.repository import AbstractSearchRepository
from app.upload.service import _to_response


class SearchService:
    def __init__(self, repo: AbstractSearchRepository) -> None:
        self._repo = repo

    async def search(
        self,
        user_id: UUID,
        query: str,
        *,
        item_type: str | None = None,
        mime_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[DriveItemResponse]:
        normalized = " ".join(query.split())
        if not normalized:
            raise AppError(ErrorCode.INVALID_OPERATION, "Search query cannot be empty")

        offset = (page - 1) * page_size
        items, total = await self._repo.search(
            user_id,
            normalized,
            item_type=item_type,
            mime_type=mime_type,
            offset=offset,
            limit=page_size,
        )
        return Page.create(
            [_to_response(i) for i in items],
            total,
            page=page,
            page_size=page_size,
        )
