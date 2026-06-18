from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.dependencies import CurrentUserId, DbSession
from app.schemas.common import DriveItemResponse, Page
from app.search.embedding import EmbeddingError
from app.search.factory import (
    build_embedding_backfill_service,
    build_semantic_search_service,
)
from app.search.repository import SQLSearchRepository
from app.search.service import SearchService
from app.upload.service import _to_response

router = APIRouter(prefix="/search", tags=["search"])


def _search_service(session: DbSession) -> SearchService:
    return SearchService(repo=SQLSearchRepository(session))


SearchServiceDep = Annotated[SearchService, Depends(_search_service)]


class SemanticHitResponse(BaseModel):
    item: DriveItemResponse
    score: float
    snippet: str


class BackfillResponse(BaseModel):
    indexed: int
    remaining: int


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


@router.get(
    "/semantic",
    response_model=list[SemanticHitResponse],
    summary="Semantic (meaning-based) search over file contents",
    responses={503: {"description": "Semantic search is not enabled / unavailable"}},
)
async def semantic_search(
    q: str,
    current_user_id: CurrentUserId,
    session: DbSession,
    limit: int = 20,
) -> list[SemanticHitResponse]:
    service = build_semantic_search_service(session, get_settings())
    if service is None:
        raise HTTPException(status_code=503, detail="Semantic search is not enabled")
    try:
        hits = await service.search(user_id=current_user_id, query=q, limit=limit)
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail="Embedding service is unavailable") from exc
    return [
        SemanticHitResponse(item=_to_response(h.item), score=h.score, snippet=h.snippet)
        for h in hits
    ]


@router.post(
    "/embeddings/backfill",
    response_model=BackfillResponse,
    summary="Backfill embeddings for your files indexed before semantic search",
    responses={503: {"description": "Semantic search is not enabled / unavailable"}},
)
async def backfill_embeddings(
    current_user_id: CurrentUserId,
    session: DbSession,
    batch_size: int = 50,
) -> BackfillResponse:
    service = build_embedding_backfill_service(session, get_settings())
    if service is None:
        raise HTTPException(status_code=503, detail="Semantic search is not enabled")
    try:
        result = await service.run(user_id=current_user_id, batch_size=batch_size)
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail="Embedding service is unavailable") from exc
    await session.commit()
    return BackfillResponse(indexed=result.indexed, remaining=result.remaining)
